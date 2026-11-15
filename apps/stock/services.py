from decimal import Decimal
from django.db import transaction
from django.db.models import Avg, F, Q, Sum
from django.utils import timezone

from apps.inventory.models import InventoryItem, Recipe, StockMovement, Supplier
from apps.menu.models import Category, Dish
from apps.orders.models import Order, OrderItem
from .models import (
    PurchaseOrder,
    PurchaseOrderItem,
    StockWastage,
    StockTransfer,
    StockTransferItem,
    StockAuditCount,
    StockAuditItem,
)


@transaction.atomic
def add_stock(
    item_id,
    quantity: Decimal,
    unit_cost: Decimal = None,
    batch_number: str = "",
    expiry_date=None,
    notes: str = "",
    performed_by=None
) -> tuple[InventoryItem, StockMovement]:
    """
    Increases inventory stock, logs purchase movement, updates batch/expiry info.
    """
    item = InventoryItem.objects.select_for_update().get(id=item_id)
    cost = unit_cost if unit_cost is not None else item.purchase_price
    qty = Decimal(str(quantity))

    item.current_stock += qty
    if unit_cost is not None and unit_cost > 0:
        item.purchase_price = unit_cost
    if batch_number:
        item.batch_number = batch_number
    if expiry_date:
        item.expiry_date = expiry_date
    item.last_restocked = timezone.now()
    item.save()

    movement = StockMovement.objects.create(
        inventory_item=item,
        movement_type=StockMovement.MovementType.PURCHASE,
        quantity=qty,
        cost_per_unit=cost,
        total_cost=(qty * cost).quantize(Decimal('0.01')),
        batch_number=batch_number or item.batch_number,
        notes=notes or "Stock added via stock management",
        performed_by=performed_by
    )

    return item, movement


@transaction.atomic
def remove_stock(
    item_id,
    quantity: Decimal,
    reason: str = "manual_removal",
    notes: str = "",
    performed_by=None
) -> tuple[InventoryItem, StockMovement]:
    """
    Decreases on-hand stock and records consumption movement.
    """
    item = InventoryItem.objects.select_for_update().get(id=item_id)
    qty = Decimal(str(quantity))

    item.current_stock = max(Decimal('0.000'), item.current_stock - qty)
    item.save(update_fields=['current_stock', 'updated_at'])

    movement = StockMovement.objects.create(
        inventory_item=item,
        movement_type=StockMovement.MovementType.CONSUMPTION,
        quantity=qty,
        cost_per_unit=item.purchase_price,
        total_cost=(qty * item.purchase_price).quantize(Decimal('0.01')),
        notes=notes or f"Stock removed: {reason}",
        performed_by=performed_by
    )

    # Check low stock notification trigger
    if item.reorder_needed:
        check_and_notify_single_item(item)

    return item, movement


@transaction.atomic
def adjust_stock(
    item_id,
    new_quantity: Decimal,
    reason: str = "count_reconciliation",
    notes: str = "",
    performed_by=None
) -> tuple[InventoryItem, StockMovement]:
    """
    Sets inventory stock directly to the reconciled actual count and logs adjustment.
    """
    item = InventoryItem.objects.select_for_update().get(id=item_id)
    new_qty = Decimal(str(new_quantity))
    variance = new_qty - item.current_stock

    item.current_stock = new_qty
    item.save(update_fields=['current_stock', 'updated_at'])

    movement = StockMovement.objects.create(
        inventory_item=item,
        movement_type=StockMovement.MovementType.ADJUSTMENT,
        quantity=variance,
        cost_per_unit=item.purchase_price,
        total_cost=(abs(variance) * item.purchase_price).quantize(Decimal('0.01')),
        notes=notes or f"Stock adjusted from {item.current_stock - variance} to {new_qty}. Reason: {reason}",
        performed_by=performed_by
    )

    return item, movement


@transaction.atomic
def record_wastage(
    item_id,
    quantity: Decimal,
    reason: str = StockWastage.Reason.SPOILED,
    notes: str = "",
    performed_by=None
) -> StockWastage:
    """
    Records spoiled, damaged, or expired stock, deducts inventory, and creates StockMovement.
    """
    item = InventoryItem.objects.select_for_update().get(id=item_id)
    qty = Decimal(str(quantity))

    wastage = StockWastage.objects.create(
        inventory_item=item,
        quantity=qty,
        unit=item.unit,
        cost_per_unit=item.purchase_price,
        reason=reason,
        notes=notes,
        logged_by=performed_by
    )

    item.current_stock = max(Decimal('0.000'), item.current_stock - qty)
    item.save(update_fields=['current_stock', 'updated_at'])

    StockMovement.objects.create(
        inventory_item=item,
        movement_type=StockMovement.MovementType.WASTE,
        quantity=qty,
        cost_per_unit=item.purchase_price,
        total_cost=wastage.total_waste_cost,
        notes=f"Wastage: {wastage.get_reason_display()} - {notes}",
        performed_by=performed_by
    )

    return wastage


def check_and_notify_single_item(item: InventoryItem):
    """Triggers low-inventory notification if item is at or below reorder level."""
    try:
        from apps.notifications.services import notify_low_inventory
        notify_low_inventory(item)
    except Exception:
        pass


def check_all_low_stock_and_notify() -> int:
    """
    Scans entire inventory for items breaching reorder thresholds and sends notifications.
    """
    items_to_alert = InventoryItem.objects.filter(
        is_active=True
    ).filter(
        Q(current_stock__lte=F('reorder_level')) | Q(current_stock__lte=F('minimum_stock'))
    )

    count = 0
    for item in items_to_alert:
        check_and_notify_single_item(item)
        count += 1
    return count


def get_inventory_valuation() -> dict:
    """
    Calculates total inventory asset valuation, category breakdowns,
    high-value ingredients, and estimated replenishment costs.
    """
    items = InventoryItem.objects.filter(is_active=True).select_related('supplier_ref')
    total_val = sum((item.stock_value for item in items), Decimal('0.00'))

    cat_map = {}
    for it in items:
        cat = it.get_category_display() if hasattr(it, 'get_category_display') else str(it.category)
        if cat not in cat_map:
            cat_map[cat] = {
                'category': cat,
                'itemsCount': 0,
                'totalValue': Decimal('0.00'),
                'totalUnits': Decimal('0.00'),
            }
        cat_map[cat]['itemsCount'] += 1
        cat_map[cat]['totalValue'] += it.stock_value
        cat_map[cat]['totalUnits'] += it.current_stock

    categories_list = sorted(cat_map.values(), key=lambda x: x['totalValue'], reverse=True)

    # Top 10 High-Value inventory assets on hand
    high_value_items = sorted(
        [
            {
                'id': str(it.id),
                'name': it.name,
                'category': it.category,
                'currentStock': float(it.current_stock),
                'unit': it.unit,
                'purchasePrice': float(it.purchase_price),
                'stockValue': float(it.stock_value),
            }
            for it in items
        ],
        key=lambda x: x['stockValue'],
        reverse=True
    )[:10]

    # Reorder required items & estimated restock cost
    reorder_items = [it for it in items if it.reorder_needed]
    est_restock_cost = Decimal('0.00')
    for rit in reorder_items:
        target = rit.reorder_level * Decimal('1.5') if rit.reorder_level > 0 else (rit.minimum_stock * Decimal('2.0'))
        diff = max(Decimal('0.00'), target - rit.current_stock)
        est_restock_cost += diff * rit.purchase_price

    return {
        'totalValuation': total_val,
        'totalItemsCount': items.count(),
        'lowStockItemsCount': len(reorder_items),
        'estimatedReplenishmentCost': est_restock_cost.quantize(Decimal('0.01')),
        'categoryBreakdown': categories_list,
        'highValueItems': high_value_items,
        'timestamp': timezone.now(),
    }


def calculate_dish_ingredient_cost(dish: Dish) -> tuple[Decimal, list]:
    """
    Calculates detailed ingredient cost per portion for a menu item from its recipe BOM.
    """
    ingredients_breakdown = []
    recipe = getattr(dish, 'recipe', None)

    if recipe and recipe.is_active:
        yields = max(1, recipe.yield_portions)
        total_cost = Decimal('0.00')
        for ing in recipe.ingredients.select_related('inventory_item').all():
            ing_cost = ing.cost
            total_cost += ing_cost
            ingredients_breakdown.append({
                'ingredientName': ing.inventory_item.name,
                'quantity': float(ing.quantity),
                'unit': ing.unit,
                'unitPurchasePrice': float(ing.inventory_item.purchase_price),
                'cost': float(ing_cost),
            })
        cost_per_portion = (total_cost / Decimal(yields)).quantize(Decimal('0.01'))
        return cost_per_portion, ingredients_breakdown

    # Fallback benchmark (30% of menu price)
    price = dish.price or Decimal('0.00')
    fallback_cost = (price * Decimal('0.30')).quantize(Decimal('0.01'))
    return fallback_cost, []


def get_food_cost_and_profitability() -> dict:
    """
    Strategic Menu Engineering & Profitability Analysis:
    - Calculates Ingredient Cost, Selling Price, Gross Margin (€), and Food Cost % for every dish.
    - Identifies:
      * Most profitable products
      * Least profitable products
      * Best sellers
      * Slow-moving products
      * High-cost ingredients
    """
    dishes = Dish.objects.filter(is_available=True).select_related('category')
    all_metrics = []

    for d in dishes:
        price = d.price or Decimal('0.00')
        ing_cost, breakdown = calculate_dish_ingredient_cost(d)
        gross_margin = price - ing_cost
        food_cost_pct = round(float((ing_cost / price) * 100), 2) if price > 0 else 0.0
        gm_pct = round(float((gross_margin / price) * 100), 2) if price > 0 else 0.0

        all_metrics.append({
            'dishId': d.id,
            'name': d.name,
            'category': d.category.name if d.category else 'General',
            'sellingPrice': price,
            'ingredientCost': ing_cost,
            'grossMargin': gross_margin,
            'grossMarginPercentage': gm_pct,
            'foodCostPercentage': food_cost_pct,
            'ordersCount': d.orders_count,
            'ingredients': breakdown,
        })

    # 1. Most profitable products (highest gross margin in €)
    most_profitable = sorted(all_metrics, key=lambda x: x['grossMargin'], reverse=True)[:8]

    # 2. Least profitable products (lowest gross margin or highest food cost %)
    least_profitable = sorted(all_metrics, key=lambda x: x['foodCostPercentage'], reverse=True)[:8]

    # 3. Best sellers (highest order volume)
    best_sellers = sorted(all_metrics, key=lambda x: x['ordersCount'], reverse=True)[:8]

    # 4. Slow-moving products (lowest order volume)
    slow_moving = sorted(all_metrics, key=lambda x: x['ordersCount'])[:8]

    # 5. High-cost raw ingredients (highest purchase price per unit in warehouse)
    high_cost_raw = InventoryItem.objects.filter(is_active=True).order_by('-purchase_price')[:10]
    high_cost_ingredients = [
        {
            'id': str(it.id),
            'name': it.name,
            'category': it.category,
            'purchasePrice': float(it.purchase_price),
            'unit': it.unit,
            'currentStock': float(it.current_stock),
            'supplierName': it.supplier or (it.supplier_ref.name if it.supplier_ref else 'None'),
        }
        for it in high_cost_raw
    ]

    return {
        'allProducts': all_metrics,
        'mostProfitableProducts': most_profitable,
        'leastProfitableProducts': least_profitable,
        'bestSellers': best_sellers,
        'slowMovingProducts': slow_moving,
        'highCostIngredients': high_cost_ingredients,
        'timestamp': timezone.now(),
    }


@transaction.atomic
def receive_purchase_order_delivery(po_id, received_items: list, invoice_number: str = "", received_by=None) -> PurchaseOrder:
    """
    Receives incoming supplier delivery:
    - Updates received quantities on PO items.
    - Adds stock to on-hand InventoryItem.
    - Records StockMovement (PURCHASE).
    - Updates PurchaseOrder status to RECEIVED or PARTIALLY_RECEIVED.
    """
    po = PurchaseOrder.objects.select_for_update().get(id=po_id)
    all_fully_received = True

    for item_data in received_items:
        po_item_id = item_data.get('item_id')
        qty_delivered = Decimal(str(item_data.get('quantity_received', 0)))
        batch = item_data.get('batch_number', '')
        expiry = item_data.get('expiry_date', None)

        try:
            po_item = po.items.select_for_update().get(id=po_item_id)
        except PurchaseOrderItem.DoesNotExist:
            continue

        po_item.quantity_received += qty_delivered
        if batch:
            po_item.batch_number = batch
        if expiry:
            po_item.expiry_date = expiry
        po_item.is_fully_received = po_item.quantity_received >= po_item.quantity_ordered
        po_item.save()

        if not po_item.is_fully_received:
            all_fully_received = False

        # Add physical stock to InventoryItem
        add_stock(
            item_id=po_item.inventory_item_id,
            quantity=qty_delivered,
            unit_cost=po_item.unit_cost,
            batch_number=batch,
            expiry_date=expiry,
            notes=f"Delivery received for {po.po_number}",
            performed_by=received_by
        )

    if invoice_number:
        po.invoice_number = invoice_number
    po.received_by = received_by
    po.actual_delivery_date = timezone.now().date()
    po.status = PurchaseOrder.Status.RECEIVED if all_fully_received else PurchaseOrder.Status.PARTIALLY_RECEIVED
    po.save()

    return po


@transaction.atomic
def reconcile_stock_audit(audit_id, performed_by=None) -> StockAuditCount:
    """
    Reconciles manual stock count session:
    Updates all inventory items to actual counted stock and logs adjustment movements.
    """
    audit = StockAuditCount.objects.select_for_update().get(id=audit_id)
    if audit.status == StockAuditCount.Status.RECONCILED:
        return audit

    for audit_item in audit.items.select_related('inventory_item').all():
        adjust_stock(
            item_id=audit_item.inventory_item_id,
            new_quantity=audit_item.actual_stock,
            reason=f"Audit Count {audit.audit_number}",
            notes=f"Count variance: {audit_item.variance} {audit_item.unit}",
            performed_by=performed_by
        )

    audit.status = StockAuditCount.Status.RECONCILED
    audit.reconciled_at = timezone.now()
    audit.save(update_fields=['status', 'reconciled_at'])
    return audit

