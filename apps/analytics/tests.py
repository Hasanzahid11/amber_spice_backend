from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.inventory.models import InventoryItem, Recipe, RecipeIngredient
from apps.menu.models import Category, Dish
from apps.orders.models import Order, OrderItem
from .models import ReportExportLog

User = get_user_model()


class AnalyticsDashboardTests(APITestCase):
    """
    Test suite for Executive Central Dashboard and Business Analytics.
    Verifies today's overview, sales trends, food costing, gross margins, and report exports.
    """

    def setUp(self):
        # Create Owner/Admin User
        self.owner_user = User.objects.create_user(
            username='owner_raj',
            email='raj@amberspice.com',
            phone='+353871239999',
            password='OwnerPassword123!',
            role=User.Role.OWNER_ADMIN,
            first_name='Raj',
            last_name='Patel'
        )
        self.client.force_authenticate(user=self.owner_user)

        # Create Categories and Dishes
        self.curry_cat = Category.objects.create(name='Curries', slug='curries')
        self.grill_cat = Category.objects.create(name='Tandoori Grills', slug='tandoori-grills')

        self.dish1 = Dish.objects.create(
            category=self.curry_cat,
            name='Butter Chicken',
            price=Decimal('16.00'),
            orders_count=15
        )
        self.dish2 = Dish.objects.create(
            category=self.grill_cat,
            name='Chicken Tikka',
            price=Decimal('14.00'),
            orders_count=8
        )

        # Create Inventory Items and Recipes for Food Cost Testing
        self.chicken = InventoryItem.objects.create(
            name='Chicken Breast',
            category='meat',
            unit='kg',
            current_stock=Decimal('4.50'),  # Low stock (<= minimum_stock 10.00)
            minimum_stock=Decimal('10.00'),
            reorder_level=Decimal('15.00'),
            purchase_price=Decimal('6.00')  # €6/kg
        )
        self.butter = InventoryItem.objects.create(
            name='Butter',
            category='dairy',
            unit='kg',
            current_stock=Decimal('15.00'),
            minimum_stock=Decimal('5.00'),
            purchase_price=Decimal('8.00')
        )

        # Recipe for Butter Chicken (yields 1 portion, uses 0.25kg chicken = €1.50, 0.05kg butter = €0.40 => food cost €1.90)
        self.recipe1 = Recipe.objects.create(dish=self.dish1, name='Butter Chicken Recipe', yield_portions=1)
        RecipeIngredient.objects.create(recipe=self.recipe1, inventory_item=self.chicken, quantity=Decimal('0.250'), unit='kg')
        RecipeIngredient.objects.create(recipe=self.recipe1, inventory_item=self.butter, quantity=Decimal('0.050'), unit='kg')

        # Create Orders Today
        # Order A: Delivery, Paid, Total €48.00 (3x Butter Chicken)
        self.order_a = Order.objects.create(
            customer_name='Alice Delivery',
            customer_phone='+353871112222',
            dining_type=Order.DiningType.DELIVERY,
            delivery_address='12 Merrion Square, Dublin',
            status=Order.Status.PREPARING,
            payment_status=Order.PaymentStatus.PAID,
            total_amount=Decimal('48.00')
        )
        OrderItem.objects.create(order=self.order_a, dish=self.dish1, name='Butter Chicken', quantity=3, price=Decimal('16.00'))

        # Order B: Takeaway / Collection, Total €28.00 (2x Chicken Tikka)
        self.order_b = Order.objects.create(
            customer_name='Bob Collection',
            customer_phone='+353873334444',
            dining_type=Order.DiningType.TAKEAWAY,
            status=Order.Status.READY,
            payment_status=Order.PaymentStatus.PAID,
            total_amount=Decimal('28.00')
        )
        OrderItem.objects.create(order=self.order_b, dish=self.dish2, name='Chicken Tikka', quantity=2, price=Decimal('14.00'))

        # Order C: Pending Dine-In, Total €16.00
        self.order_c = Order.objects.create(
            customer_name='Charlie Dine-in',
            customer_phone='+353875556666',
            dining_type=Order.DiningType.DINE_IN,
            table_number='T1',
            status=Order.Status.PENDING,
            payment_status=Order.PaymentStatus.PENDING,
            total_amount=Decimal('16.00')
        )
        OrderItem.objects.create(order=self.order_c, dish=self.dish1, name='Butter Chicken', quantity=1, price=Decimal('16.00'))

    def test_legacy_summary_endpoint_backward_compatibility(self):
        """
        Ensures GET /api/v1/analytics/summary/ preserves all existing keys and contracts.
        """
        response = self.client.get('/api/v1/analytics/summary/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertIn('totalRevenue', data)
        self.assertIn('todayRevenue', data)
        self.assertIn('totalOrders', data)
        self.assertIn('todayOrders', data)
        self.assertIn('activeKitchenOrders', data)
        self.assertIn('tables', data)
        self.assertIn('lowStockAlerts', data)
        self.assertIn('topDishes', data)
        self.assertIn('timestamp', data)
        self.assertIn('todayOverview', data)

    def test_today_dashboard_overview_metrics(self):
        """
        Tests GET /api/v1/analytics/dashboard/ for Today's Overview requirements:
        Total sales, order count, AOV, delivery sales, collection sales,
        best-selling products, low-stock items, pending orders.
        """
        response = self.client.get('/api/v1/analytics/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        # Total Sales: €48 + €28 + €16 = €92.00
        self.assertEqual(Decimal(str(data['totalSales'])), Decimal('92.00'))
        self.assertEqual(data['orderCount'], 3)
        # AOV: 92 / 3 = €30.67
        self.assertEqual(Decimal(str(data['averageOrderValue'])), Decimal('30.67'))

        # Delivery sales: €48.00 (1 order)
        self.assertEqual(Decimal(str(data['deliverySales'])), Decimal('48.00'))
        self.assertEqual(data['deliveryOrderCount'], 1)

        # Collection sales: €28.00 (1 order)
        self.assertEqual(Decimal(str(data['collectionSales'])), Decimal('28.00'))
        self.assertEqual(data['collectionOrderCount'], 1)

        # Dine-in sales: €16.00 (1 order)
        self.assertEqual(Decimal(str(data['dineInSales'])), Decimal('16.00'))
        self.assertEqual(data['dineInOrderCount'], 1)

        # Best-selling products: Butter Chicken should be #1 (4 portions sold)
        best_sellers = data['bestSellingProducts']
        self.assertGreaterEqual(len(best_sellers), 1)
        self.assertEqual(best_sellers[0]['name'], 'Butter Chicken')
        self.assertEqual(best_sellers[0]['quantitySold'], 4)

        # Current Low-stock items: Chicken Breast is 4.5kg <= 10.0kg
        low_stock = data['lowStockItems']
        self.assertGreaterEqual(len(low_stock), 1)
        chicken_alert = [item for item in low_stock if item['name'] == 'Chicken Breast'][0]
        self.assertEqual(chicken_alert['currentStock'], 4.5)
        self.assertEqual(chicken_alert['minimumStock'], 10.0)

        # Pending orders: Order C is in PENDING status
        pending = data['pendingOrders']
        self.assertGreaterEqual(len(pending), 1)
        self.assertEqual(pending[0]['customerName'], 'Charlie Dine-in')

    def test_sales_analytics_time_series(self):
        """
        Tests GET /api/v1/analytics/sales/?period=daily|weekly|monthly
        """
        # Daily
        res_daily = self.client.get('/api/v1/analytics/sales/?period=daily')
        self.assertEqual(res_daily.status_code, status.HTTP_200_OK)
        self.assertIn('series', res_daily.data)
        self.assertIn('summary', res_daily.data)
        self.assertEqual(Decimal(str(res_daily.data['summary']['totalSales'])), Decimal('92.00'))

        # Weekly
        res_weekly = self.client.get('/api/v1/analytics/sales/?period=weekly')
        self.assertEqual(res_weekly.status_code, status.HTTP_200_OK)
        self.assertEqual(res_weekly.data['periodType'], 'weekly')

        # Monthly
        res_monthly = self.client.get('/api/v1/analytics/sales/?period=monthly')
        self.assertEqual(res_monthly.status_code, status.HTTP_200_OK)
        self.assertEqual(res_monthly.data['periodType'], 'monthly')

    def test_product_sales_and_food_cost_margins(self):
        """
        Tests GET /api/v1/analytics/products/ calculates recipe food cost and gross margins.
        """
        res = self.client.get('/api/v1/analytics/products/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        products = res.data
        self.assertGreaterEqual(len(products), 2)

        butter_chicken = [p for p in products if p['name'] == 'Butter Chicken'][0]
        self.assertEqual(butter_chicken['quantitySold'], 4)
        self.assertEqual(Decimal(str(butter_chicken['totalRevenue'])), Decimal('64.00'))
        # Recipe cost per portion was €1.90
        self.assertEqual(Decimal(str(butter_chicken['foodCostPerUnit'])), Decimal('1.90'))
        # Total food cost: 4 * €1.90 = €7.60
        self.assertEqual(Decimal(str(butter_chicken['totalFoodCost'])), Decimal('7.60'))
        # Estimated gross margin: €64.00 - €7.60 = €56.40
        self.assertEqual(Decimal(str(butter_chicken['estimatedGrossMargin'])), Decimal('56.40'))

    def test_sales_by_category_and_channels(self):
        """
        Tests GET /api/v1/analytics/categories/ and /api/v1/analytics/channels/
        """
        # Categories
        res_cat = self.client.get('/api/v1/analytics/categories/')
        self.assertEqual(res_cat.status_code, status.HTTP_200_OK)
        cat_names = [c['name'] for c in res_cat.data]
        self.assertIn('Curries', cat_names)
        self.assertIn('Tandoori Grills', cat_names)

        # Channels
        res_ch = self.client.get('/api/v1/analytics/channels/')
        self.assertEqual(res_ch.status_code, status.HTTP_200_OK)
        channels = {c['channel']: c for c in res_ch.data}
        self.assertIn('Delivery', channels)
        self.assertIn('Collection / Takeaway', channels)
        self.assertIn('Dine-In', channels)
        self.assertEqual(Decimal(str(channels['Delivery']['totalSales'])), Decimal('48.00'))

    def test_business_performance_metrics(self):
        """
        Tests GET /api/v1/analytics/performance/ for food cost percentage and peak hours.
        """
        res = self.client.get('/api/v1/analytics/performance/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data

        self.assertIn('totalRevenue', data)
        self.assertIn('foodCost', data)
        self.assertIn('foodCostPercentage', data)
        self.assertIn('estimatedGrossMargin', data)
        self.assertIn('grossMarginPercentage', data)
        self.assertEqual(len(data['hourlyVolume']), 24)
        self.assertEqual(len(data['dayOfWeekVolume']), 7)

    def test_reports_export_csv_and_excel(self):
        """
        Tests GET /api/v1/analytics/reports/export/?report_type=sales_by_product&format=csv
        and format=excel, format=html.
        """
        # CSV Export
        csv_res = self.client.get('/api/v1/analytics/reports/export/?report_type=sales_by_product&format=csv')
        self.assertEqual(csv_res.status_code, status.HTTP_200_OK)
        self.assertEqual(csv_res['Content-Type'], 'text/csv; charset=utf-8')
        content = csv_res.content.decode('utf-8')
        self.assertIn('Butter Chicken', content)
        self.assertIn('Gross Margin', content)

        # Excel Export
        excel_res = self.client.get('/api/v1/analytics/reports/export/?report_type=sales_by_channel&format=excel')
        self.assertEqual(excel_res.status_code, status.HTTP_200_OK)
        self.assertEqual(excel_res['Content-Type'], 'application/vnd.ms-excel; charset=utf-8')

        # HTML / PDF Print Export
        html_res = self.client.get('/api/v1/analytics/reports/export/?report_type=daily_sales&format=html')
        self.assertEqual(html_res.status_code, status.HTTP_200_OK)
        self.assertIn('text/html', html_res['Content-Type'])
        self.assertIn('window.print()', html_res.content.decode('utf-8'))

        # Verify export audit logs
        logs = ReportExportLog.objects.filter(generated_by=self.owner_user)
        self.assertEqual(logs.count(), 3)
