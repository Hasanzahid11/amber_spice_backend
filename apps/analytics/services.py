import csv
import io
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.db.models import Avg, Count, F, Q, Sum
from django.utils import timezone

from apps.inventory.models import InventoryItem, Recipe, StockMovement
from apps.menu.models import Category, Dish
from apps.orders.models import Order, OrderItem
from apps.reservations.models import Table
from .models import DailySalesSnapshot, ReportExportLog


def calculate_dish_unit_cost(dish: Dish) -> Decimal:
    """
    Computes recipe-based ingredient cost per portion for a given Dish.
    If no recipe exists, defaults to estimated 30% standard food cost benchmark.
    """
    if not dish:
        return Decimal('0.00')

    try:
        recipe = getattr(dish, 'recipe', None)
        if recipe and recipe.is_active:
            yields = max(1, recipe.yield_portions)
            total_recipe_cost = Decimal('0.00')
            for ing in recipe.ingredients.select_related('inventory_item').all():
                total_recipe_cost += ing.cost
            return (total_recipe_cost / Decimal(yields)).quantize(Decimal('0.01'))
    except Exception:
        pass

    # Standard fallback benchmark (30% of menu price)
    price = dish.price or Decimal('0.00')
    return (price * Decimal('0.30')).quantize(Decimal('0.01'))


def get_today_overview() -> dict:
    """
    Returns today's real-time executive dashboard overview for Owner/Admin.
    """
    now = timezone.now()
    today = now.date()

    orders_today_all = Order.objects.filter(created_at__date=today)
    valid_orders = orders_today_all.exclude(status=Order.Status.CANCELLED)

    total_sales = sum((o.total_amount for o in valid_orders), Decimal('0.00'))
    order_count = valid_orders.count()
    aov = (total_sales / Decimal(order_count)).quantize(Decimal('0.01')) if order_count > 0 else Decimal('0.00')

    # Channel breakdowns
    delivery_orders = valid_orders.filter(dining_type=Order.DiningType.DELIVERY)
    delivery_sales = sum((o.total_amount for o in delivery_orders), Decimal('0.00'))
    delivery_count = delivery_orders.count()

    collection_orders = valid_orders.filter(dining_type=Order.DiningType.TAKEAWAY)
    collection_sales = sum((o.total_amount for o in collection_orders), Decimal('0.00'))
    collection_count = collection_orders.count()

    dine_in_orders = valid_orders.filter(dining_type=Order.DiningType.DINE_IN)
    dine_in_sales = sum((o.total_amount for o in dine_in_orders), Decimal('0.00'))
    dine_in_count = dine_in_orders.count()

    # Best-selling products today
    items_today = OrderItem.objects.filter(order__in=valid_orders).select_related('dish', 'dish__category')
    dish_sales_map = {}
    for it in items_today:
        dish_id = it.dish_id or it.name
        if dish_id not in dish_sales_map:
            category_name = it.dish.category.name if (it.dish and it.dish.category) else 'General'
            dish_sales_map[dish_id] = {
                'dishId': it.dish_id,
                'name': it.name,
                'category': category_name,
                'unitPrice': it.price,
                'quantitySold': 0,
                'revenue': Decimal('0.00'),
            }
        dish_sales_map[dish_id]['quantitySold'] += it.quantity
        dish_sales_map[dish_id]['revenue'] += it.price * Decimal(it.quantity)

    best_selling_today = sorted(dish_sales_map.values(), key=lambda x: x['quantitySold'], reverse=True)[:10]

    # If few or no orders today yet, supplement with top menu performers
    if not best_selling_today:
        top_menu = Dish.objects.filter(is_available=True).select_related('category').order_by('-orders_count')[:5]
        for d in top_menu:
            best_selling_today.append({
                'dishId': d.id,
                'name': d.name,
                'category': d.category.name if d.category else 'General',
                'unitPrice': d.price,
                'quantitySold': d.orders_count,
                'revenue': d.price * Decimal(d.orders_count),
            })

    # Current low-stock items
    low_stock_qs = InventoryItem.objects.filter(
        current_stock__lte=F('minimum_stock')
    ).select_related('supplier').order_by('current_stock')[:15]

    low_stock_list = []
    for item in low_stock_qs:
        low_stock_list.append({
            'id': str(item.id),
            'name': item.name,
            'category': item.get_category_display() if hasattr(item, 'get_category_display') else str(item.category),
            'currentStock': float(item.current_stock),
            'minimumStock': float(item.minimum_stock),
            'reorderLevel': float(item.reorder_level) if hasattr(item, 'reorder_level') and item.reorder_level else float(item.minimum_stock),
            'unit': item.unit,
            'supplierName': item.supplier.name if item.supplier else 'None',
            'purchasePrice': float(item.purchase_price),
        })

    # Pending orders requiring kitchen or front-of-house attention
    pending_qs = Order.objects.filter(status=Order.Status.PENDING).order_by('created_at')[:20]
    pending_list = []
    for po in pending_qs:
        pending_list.append({
            'id': str(po.id),
            'orderNumber': po.order_number,
            'customerName': po.customer_name,
            'customerPhone': po.customer_phone,
            'diningType': po.dining_type,
            'diningTypeDisplay': po.get_dining_type_display(),
            'totalAmount': float(po.total_amount),
            'priority': po.priority,
            'elapsedMinutes': po.elapsed_minutes,
            'createdAt': po.created_at.isoformat(),
        })

    # Kitchen & Table metrics
    active_kitchen_count = Order.objects.filter(
        status__in=[Order.Status.PENDING, Order.Status.PREPARING, Order.Status.READY]
    ).count()

    total_tables = Table.objects.count()
    occupied_tables = Table.objects.filter(status='occupied').count()
    available_tables = Table.objects.filter(status='available').count()

    return {
        'todayDate': today,
        'totalSales': total_sales,
        'orderCount': order_count,
        'averageOrderValue': aov,
        'deliverySales': delivery_sales,
        'deliveryOrderCount': delivery_count,
        'collectionSales': collection_sales,
        'collectionOrderCount': collection_count,
        'dineInSales': dine_in_sales,
        'dineInOrderCount': dine_in_count,
        'bestSellingProducts': best_selling_today,
        'lowStockItems': low_stock_list,
        'pendingOrders': pending_list,
        'activeKitchenCount': active_kitchen_count,
        'tables': {
            'total': total_tables,
            'occupied': occupied_tables,
            'available': available_tables,
        },
        'timestamp': now,
    }


def get_sales_analytics(period: str = 'daily', start_date: date = None, end_date: date = None) -> dict:
    """
    Computes business sales analytics across Daily, Weekly, or Monthly buckets.
    """
    now = timezone.now()
    if not end_date:
        end_date = now.date()

    if not start_date:
        if period == 'monthly':
            start_date = end_date - timedelta(days=365)
        elif period == 'weekly':
            start_date = end_date - timedelta(days=84)  # 12 weeks
        else:
            start_date = end_date - timedelta(days=30)  # 30 days

    orders = Order.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).exclude(status=Order.Status.CANCELLED)

    buckets = {}

    if period == 'monthly':
        # Group by Year-Month
        curr = start_date.replace(day=1)
        while curr <= end_date:
            key = curr.strftime('%Y-%m')
            buckets[key] = {
                'period': curr.strftime('%B %Y'),
                'date': curr,
                'totalSales': Decimal('0.00'),
                'orderCount': 0,
                'deliverySales': Decimal('0.00'),
                'collectionSales': Decimal('0.00'),
                'dineInSales': Decimal('0.00'),
            }
            # Next month
            year = curr.year + (curr.month // 12)
            month = (curr.month % 12) + 1
            curr = date(year, month, 1)

        for o in orders:
            key = o.created_at.strftime('%Y-%m')
            if key in buckets:
                buckets[key]['totalSales'] += o.total_amount
                buckets[key]['orderCount'] += 1
                if o.dining_type == Order.DiningType.DELIVERY:
                    buckets[key]['deliverySales'] += o.total_amount
                elif o.dining_type == Order.DiningType.TAKEAWAY:
                    buckets[key]['collectionSales'] += o.total_amount
                elif o.dining_type == Order.DiningType.DINE_IN:
                    buckets[key]['dineInSales'] += o.total_amount

    elif period == 'weekly':
        # Group by ISO week
        curr = start_date - timedelta(days=start_date.weekday())  # Start on Monday
        while curr <= end_date:
            key = f"{curr.year}-W{curr.isocalendar()[1]:02d}"
            week_end = curr + timedelta(days=6)
            buckets[key] = {
                'period': f"Week of {curr.strftime('%d %b %Y')}",
                'date': curr,
                'totalSales': Decimal('0.00'),
                'orderCount': 0,
                'deliverySales': Decimal('0.00'),
                'collectionSales': Decimal('0.00'),
                'dineInSales': Decimal('0.00'),
            }
            curr += timedelta(days=7)

        for o in orders:
            iso = o.created_at.isocalendar()
            key = f"{iso[0]}-W{iso[1]:02d}"
            if key in buckets:
                buckets[key]['totalSales'] += o.total_amount
                buckets[key]['orderCount'] += 1
                if o.dining_type == Order.DiningType.DELIVERY:
                    buckets[key]['deliverySales'] += o.total_amount
                elif o.dining_type == Order.DiningType.TAKEAWAY:
                    buckets[key]['collectionSales'] += o.total_amount
                elif o.dining_type == Order.DiningType.DINE_IN:
                    buckets[key]['dineInSales'] += o.total_amount

    else:
        # Daily
        curr = start_date
        while curr <= end_date:
            key = curr.isoformat()
            buckets[key] = {
                'period': curr.strftime('%a, %d %b %Y'),
                'date': curr,
                'totalSales': Decimal('0.00'),
                'orderCount': 0,
                'deliverySales': Decimal('0.00'),
                'collectionSales': Decimal('0.00'),
                'dineInSales': Decimal('0.00'),
            }
            curr += timedelta(days=1)

        for o in orders:
            key = o.created_at.date().isoformat()
            if key in buckets:
                buckets[key]['totalSales'] += o.total_amount
                buckets[key]['orderCount'] += 1
                if o.dining_type == Order.DiningType.DELIVERY:
                    buckets[key]['deliverySales'] += o.total_amount
                elif o.dining_type == Order.DiningType.TAKEAWAY:
                    buckets[key]['collectionSales'] += o.total_amount
                elif o.dining_type == Order.DiningType.DINE_IN:
                    buckets[key]['dineInSales'] += o.total_amount

    # Compute AOV per bucket
    series = []
    grand_total_sales = Decimal('0.00')
    grand_order_count = 0

    for b in buckets.values():
        cnt = b['orderCount']
        tot = b['totalSales']
        b['averageOrderValue'] = (tot / Decimal(cnt)).quantize(Decimal('0.01')) if cnt > 0 else Decimal('0.00')
        grand_total_sales += tot
        grand_order_count += cnt
        series.append(b)

    grand_aov = (grand_total_sales / Decimal(grand_order_count)).quantize(Decimal('0.01')) if grand_order_count > 0 else Decimal('0.00')

    return {
        'periodType': period,
        'startDate': start_date,
        'endDate': end_date,
        'summary': {
            'totalSales': grand_total_sales,
            'orderCount': grand_order_count,
            'averageOrderValue': grand_aov,
        },
        'series': series,
    }


def get_sales_by_product(start_date: date = None, end_date: date = None) -> list:
    """
    Returns itemized product breakdown with quantities, revenue, food cost, and margins.
    """
    now = timezone.now()
    if not end_date:
        end_date = now.date()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    orders = Order.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).exclude(status=Order.Status.CANCELLED)

    order_items = OrderItem.objects.filter(order__in=orders).select_related('dish', 'dish__category')
    total_revenue_all = sum((it.price * Decimal(it.quantity) for it in order_items), Decimal('0.00'))

    product_map = {}
    for it in order_items:
        key = it.dish_id or it.name
        if key not in product_map:
            category_name = it.dish.category.name if (it.dish and it.dish.category) else 'General'
            unit_cost = calculate_dish_unit_cost(it.dish)
            product_map[key] = {
                'dishId': it.dish_id,
                'name': it.name,
                'category': category_name,
                'unitPrice': it.price,
                'quantitySold': 0,
                'totalRevenue': Decimal('0.00'),
                'foodCostPerUnit': unit_cost,
                'totalFoodCost': Decimal('0.00'),
            }
        product_map[key]['quantitySold'] += it.quantity
        rev = it.price * Decimal(it.quantity)
        product_map[key]['totalRevenue'] += rev
        product_map[key]['totalFoodCost'] += product_map[key]['foodCostPerUnit'] * Decimal(it.quantity)

    results = []
    for p in product_map.values():
        rev = p['totalRevenue']
        pct = round(float((rev / total_revenue_all) * 100), 2) if total_revenue_all > 0 else 0.0
        gm = p['totalRevenue'] - p['totalFoodCost']
        gm_pct = round(float((gm / rev) * 100), 2) if rev > 0 else 0.0
        p['revenuePercentage'] = pct
        p['estimatedGrossMargin'] = gm
        p['grossMarginPercentage'] = gm_pct
        results.append(p)

    results.sort(key=lambda x: x['totalRevenue'], reverse=True)
    return results


def get_sales_by_category(start_date: date = None, end_date: date = None) -> list:
    """
    Returns sales aggregated by category.
    """
    products = get_sales_by_product(start_date, end_date)
    total_sales = sum((p['totalRevenue'] for p in products), Decimal('0.00'))

    cat_map = {}
    for p in products:
        cname = p['category']
        if cname not in cat_map:
            cat_map[cname] = {
                'categoryId': None,
                'name': cname,
                'itemsCount': 0,
                'quantitySold': 0,
                'totalRevenue': Decimal('0.00'),
            }
        cat_map[cname]['itemsCount'] += 1
        cat_map[cname]['quantitySold'] += p['quantitySold']
        cat_map[cname]['totalRevenue'] += p['totalRevenue']

    results = []
    for c in cat_map.values():
        rev = c['totalRevenue']
        pct = round(float((rev / total_sales) * 100), 2) if total_sales > 0 else 0.0
        c['revenuePercentage'] = pct
        results.append(c)

    results.sort(key=lambda x: x['totalRevenue'], reverse=True)
    return results


def get_sales_by_channel(start_date: date = None, end_date: date = None) -> list:
    """
    Returns sales split by delivery, collection/takeaway, and dine-in channels.
    """
    now = timezone.now()
    if not end_date:
        end_date = now.date()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    orders = Order.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).exclude(status=Order.Status.CANCELLED)

    total_sales = sum((o.total_amount for o in orders), Decimal('0.00'))
    total_count = orders.count()

    channels = [
        {'channel': 'Delivery', 'channelCode': Order.DiningType.DELIVERY},
        {'channel': 'Collection / Takeaway', 'channelCode': Order.DiningType.TAKEAWAY},
        {'channel': 'Dine-In', 'channelCode': Order.DiningType.DINE_IN},
    ]

    results = []
    for ch in channels:
        ch_orders = orders.filter(dining_type=ch['channelCode'])
        ch_sales = sum((o.total_amount for o in ch_orders), Decimal('0.00'))
        ch_count = ch_orders.count()
        ch_aov = (ch_sales / Decimal(ch_count)).quantize(Decimal('0.01')) if ch_count > 0 else Decimal('0.00')

        sales_pct = round(float((ch_sales / total_sales) * 100), 2) if total_sales > 0 else 0.0
        order_pct = round(float((ch_count / total_count) * 100), 2) if total_count > 0 else 0.0

        results.append({
            'channel': ch['channel'],
            'channelCode': ch['channelCode'],
            'totalSales': ch_sales,
            'orderCount': ch_count,
            'averageOrderValue': ch_aov,
            'salesPercentage': sales_pct,
            'orderPercentage': order_pct,
        })

    return results


def get_business_performance(start_date: date = None, end_date: date = None) -> dict:
    """
    Computes holistic business performance: total revenue, order volume, AOV,
    food costing, gross margins, hourly volume distribution, and day-of-week trends.
    """
    now = timezone.now()
    if not end_date:
        end_date = now.date()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    orders = Order.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).exclude(status=Order.Status.CANCELLED)

    total_revenue = sum((o.total_amount for o in orders), Decimal('0.00'))
    order_volume = orders.count()
    aov = (total_revenue / Decimal(order_volume)).quantize(Decimal('0.01')) if order_volume > 0 else Decimal('0.00')

    # Food cost from order items
    order_items = OrderItem.objects.filter(order__in=orders).select_related('dish')
    total_food_cost = Decimal('0.00')
    for it in order_items:
        unit_cost = calculate_dish_unit_cost(it.dish)
        total_food_cost += unit_cost * Decimal(it.quantity)

    food_cost_pct = round(float((total_food_cost / total_revenue) * 100), 2) if total_revenue > 0 else 0.0
    gross_margin = total_revenue - total_food_cost
    gross_margin_pct = round(float((gross_margin / total_revenue) * 100), 2) if total_revenue > 0 else 0.0

    # Hourly distribution (00:00 to 23:00)
    hourly_map = {h: {'hour': h, 'hourDisplay': f"{h:02d}:00", 'orderCount': 0, 'revenue': Decimal('0.00')} for h in range(24)}
    # Day of week distribution (0 = Mon, 6 = Sun)
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    dow_map = {d: {'dayOfWeek': d, 'dayName': day_names[d], 'orderCount': 0, 'revenue': Decimal('0.00')} for d in range(7)}

    for o in orders:
        h = o.created_at.hour
        hourly_map[h]['orderCount'] += 1
        hourly_map[h]['revenue'] += o.total_amount

        d = o.created_at.weekday()
        dow_map[d]['orderCount'] += 1
        dow_map[d]['revenue'] += o.total_amount

    return {
        'totalRevenue': total_revenue,
        'orderVolume': order_volume,
        'averageOrderValue': aov,
        'foodCost': total_food_cost,
        'foodCostPercentage': food_cost_pct,
        'estimatedGrossMargin': gross_margin,
        'grossMarginPercentage': gross_margin_pct,
        'hourlyVolume': list(hourly_map.values()),
        'dayOfWeekVolume': list(dow_map.values()),
        'timestamp': now,
    }


def generate_report_csv(report_type: str, start_date: date = None, end_date: date = None) -> tuple[str, int]:
    """
    Generates CSV string and row count for financial and operational reports.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == 'sales_by_product':
        writer.writerow(['Product Name', 'Category', 'Unit Price (€)', 'Quantity Sold', 'Total Revenue (€)', '% of Sales', 'Food Cost / Unit (€)', 'Total Food Cost (€)', 'Gross Margin (€)', 'Gross Margin %'])
        products = get_sales_by_product(start_date, end_date)
        for p in products:
            writer.writerow([
                p['name'],
                p['category'],
                f"{p['unitPrice']:.2f}",
                p['quantitySold'],
                f"{p['totalRevenue']:.2f}",
                f"{p['revenuePercentage']:.2f}%",
                f"{p['foodCostPerUnit']:.2f}",
                f"{p['totalFoodCost']:.2f}",
                f"{p['estimatedGrossMargin']:.2f}",
                f"{p['grossMarginPercentage']:.2f}%",
            ])
        return output.getvalue(), len(products)

    elif report_type == 'sales_by_category':
        writer.writerow(['Category', 'Dishes Count', 'Quantity Sold', 'Total Revenue (€)', '% of Sales'])
        cats = get_sales_by_category(start_date, end_date)
        for c in cats:
            writer.writerow([
                c['name'],
                c['itemsCount'],
                c['quantitySold'],
                f"{c['totalRevenue']:.2f}",
                f"{c['revenuePercentage']:.2f}%",
            ])
        return output.getvalue(), len(cats)

    elif report_type == 'sales_by_channel':
        writer.writerow(['Channel', 'Total Sales (€)', 'Orders Count', 'Average Order Value (€)', '% of Sales', '% of Orders'])
        channels = get_sales_by_channel(start_date, end_date)
        for ch in channels:
            writer.writerow([
                ch['channel'],
                f"{ch['totalSales']:.2f}",
                ch['orderCount'],
                f"{ch['averageOrderValue']:.2f}",
                f"{ch['salesPercentage']:.2f}%",
                f"{ch['orderPercentage']:.2f}%",
            ])
        return output.getvalue(), len(channels)

    elif report_type == 'low_stock_items':
        writer.writerow(['Item Name', 'Category', 'Current Stock', 'Min Stock', 'Reorder Level', 'Unit', 'Supplier', 'Cost / Unit (€)'])
        items = InventoryItem.objects.filter(current_stock__lte=F('minimum_stock')).select_related('supplier')
        count = 0
        for it in items:
            writer.writerow([
                it.name,
                it.get_category_display() if hasattr(it, 'get_category_display') else str(it.category),
                f"{it.current_stock:.2f}",
                f"{it.minimum_stock:.2f}",
                f"{it.reorder_level:.2f}" if hasattr(it, 'reorder_level') and it.reorder_level else '',
                it.unit,
                it.supplier.name if it.supplier else '',
                f"{it.purchase_price:.2f}",
            ])
            count += 1
        return output.getvalue(), count

    else:
        # Default: Daily sales trend
        writer.writerow(['Date / Period', 'Total Sales (€)', 'Orders Count', 'Average Order Value (€)', 'Delivery Sales (€)', 'Collection Sales (€)', 'Dine-In Sales (€)'])
        res = get_sales_analytics(period='daily', start_date=start_date, end_date=end_date)
        series = res['series']
        for row in series:
            writer.writerow([
                row['period'],
                f"{row['totalSales']:.2f}",
                row['orderCount'],
                f"{row['averageOrderValue']:.2f}",
                f"{row['deliverySales']:.2f}",
                f"{row['collectionSales']:.2f}",
                f"{row['dineInSales']:.2f}",
            ])
        return output.getvalue(), len(series)


def generate_report_html(report_type: str, start_date: date = None, end_date: date = None) -> str:
    """
    Generates clean printable HTML report with Amber Spice branding and PDF-ready formatting.
    """
    csv_data, row_count = generate_report_csv(report_type, start_date, end_date)
    reader = csv.reader(io.StringIO(csv_data))
    rows = list(reader)

    title = report_type.replace('_', ' ').title()
    date_range_str = f"{start_date or 'Past 30 Days'} to {end_date or 'Today'}"

    headers = rows[0] if rows else []
    body_rows = rows[1:] if len(rows) > 1 else []

    table_header_html = "".join([f"<th style='padding: 10px; border-bottom: 2px solid #333; text-align: left; background: #fafafa;'>{h}</th>" for h in headers])
    table_body_html = ""
    for r in body_rows:
        tds = "".join([f"<td style='padding: 8px 10px; border-bottom: 1px solid #e0e0e0;'>{col}</td>" for col in r])
        table_body_html += f"<tr>{tds}</tr>"

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Amber Spice - {title} Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #222; margin: 30px; }}
        .header {{ border-bottom: 3px solid #D32F2F; padding-bottom: 15px; margin-bottom: 25px; }}
        .header h1 {{ color: #D32F2F; margin: 0 0 5px 0; font-size: 26px; }}
        .header .meta {{ color: #666; font-size: 14px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; }}
        .print-btn {{ background: #D32F2F; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 14px; margin-bottom: 15px; }}
        @media print {{
            .print-btn {{ display: none; }}
            body {{ margin: 0; }}
        }}
    </style>
</head>
<body>
    <button class="print-btn" onclick="window.print()">Print / Save as PDF</button>
    <div class="header">
        <h1>Amber Spice Restaurant</h1>
        <div class="meta">
            <strong>{title} Report</strong> | Date Range: {date_range_str} | Generated: {timezone.now().strftime('%Y-%m-%d %H:%M')}
        </div>
    </div>
    <table>
        <thead>
            <tr>{table_header_html}</tr>
        </thead>
        <tbody>
            {table_body_html}
        </tbody>
    </table>
</body>
</html>"""
    return html

