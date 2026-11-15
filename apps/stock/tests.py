from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.inventory.models import InventoryItem, Recipe, RecipeIngredient, Supplier
from apps.menu.models import Category, Dish
from apps.notifications.models import Notification
from .models import (
    PurchaseOrder,
    PurchaseOrderItem,
    StockWastage,
    StockTransfer,
    StockAuditCount,
    StockAuditItem,
)

User = get_user_model()


class StockManagementSystemTests(APITestCase):
    """
    Test suite for Stock & Supplier Management and Food Cost Profitability.
    Verifies adding/removing/adjusting stock, recording wastage/damage, stock transfers,
    manual stock counts, inventory valuation, PO delivery receiving, and profitability calculations.
    """

    def setUp(self):
        # Manager / Admin User
        self.manager = User.objects.create_user(
            username='manager_stock',
            email='manager@amberspice.com',
            phone='+353871234567',
            password='Password123!',
            role=User.Role.MANAGER,
            first_name='Chef',
            last_name='Manager'
        )
        self.client.force_authenticate(user=self.manager)

        # Supplier
        self.supplier = Supplier.objects.create(
            name='Dublin Meats & Poultry Ltd',
            contact_name='Liam O’Connor',
            email='orders@dublinmeats.ie',
            phone='+35318889999',
            lead_time_days=2
        )

        # Inventory Items
        self.chicken = InventoryItem.objects.create(
            name='Fresh Chicken Fillet',
            category='Meat & Poultry',
            unit='kg',
            current_stock=Decimal('10.000'),
            minimum_stock=Decimal('5.000'),
            reorder_level=Decimal('8.000'),
            purchase_price=Decimal('6.50'),
            supplier_ref=self.supplier
        )

        self.rice = InventoryItem.objects.create(
            name='Basmati Royal Rice',
            category='Rice & Grains',
            unit='kg',
            current_stock=Decimal('20.000'),
            minimum_stock=Decimal('10.000'),
            reorder_level=Decimal('15.000'),
            purchase_price=Decimal('2.20')
        )

        self.saffron = InventoryItem.objects.create(
            name='Pure Spanish Saffron',
            category='Spices & Seasoning',
            unit='g',
            current_stock=Decimal('50.000'),
            minimum_stock=Decimal('20.000'),
            purchase_price=Decimal('12.00')  # High-cost ingredient
        )

        # Menu Category & Dishes
        self.category = Category.objects.create(name='Curries', slug='curries')
        self.chicken_curry = Dish.objects.create(
            category=self.category,
            name='Chicken Tikka Masala',
            price=Decimal('16.00'),
            orders_count=120
        )
        self.slow_dish = Dish.objects.create(
            category=self.category,
            name='Exotic Saffron Prawn',
            price=Decimal('24.00'),
            orders_count=5
        )

        # Recipe for Chicken Tikka Masala: 0.25kg chicken = €1.63
        self.recipe = Recipe.objects.create(dish=self.chicken_curry, name='Chicken Tikka Recipe', yield_portions=1)
        RecipeIngredient.objects.create(recipe=self.recipe, inventory_item=self.chicken, quantity=Decimal('0.250'), unit='kg')

    def test_stock_operations_add_remove_adjust_wastage(self):
        """
        Tests Add stock, Remove stock, Adjust stock, and Record wastage.
        """
        # 1. Add Stock (+5kg Chicken)
        res_add = self.client.post('/api/v1/stock/add/', {
            'item_id': str(self.chicken.id),
            'quantity': '5.000',
            'unit_cost': '6.80',
            'batch_number': 'LOT-CHICK-101'
        })
        self.assertEqual(res_add.status_code, status.HTTP_200_OK)
        self.chicken.refresh_from_db()
        self.assertEqual(self.chicken.current_stock, Decimal('15.000'))
        self.assertEqual(self.chicken.purchase_price, Decimal('6.80'))

        # 2. Remove Stock (-3kg Chicken)
        res_rem = self.client.post('/api/v1/stock/remove/', {
            'item_id': str(self.chicken.id),
            'quantity': '3.000',
            'reason': 'kitchen_service'
        })
        self.assertEqual(res_rem.status_code, status.HTTP_200_OK)
        self.chicken.refresh_from_db()
        self.assertEqual(self.chicken.current_stock, Decimal('12.000'))

        # 3. Adjust Stock (Reconciled to 11.5kg)
        res_adj = self.client.post('/api/v1/stock/adjust/', {
            'item_id': str(self.chicken.id),
            'new_quantity': '11.500',
            'reason': 'Scale discrepancy'
        })
        self.assertEqual(res_adj.status_code, status.HTTP_200_OK)
        self.chicken.refresh_from_db()
        self.assertEqual(self.chicken.current_stock, Decimal('11.500'))

        # 4. Record Wastage (1.5kg Spoiled)
        res_waste = self.client.post('/api/v1/stock/wastage/', {
            'item_id': str(self.chicken.id),
            'quantity': '1.500',
            'reason': StockWastage.Reason.SPOILED,
            'notes': 'Overnight fridge power cut'
        })
        self.assertEqual(res_waste.status_code, status.HTTP_201_CREATED)
        self.chicken.refresh_from_db()
        self.assertEqual(self.chicken.current_stock, Decimal('10.000'))
        self.assertEqual(StockWastage.objects.count(), 1)

    def test_low_stock_notification_alert_generation(self):
        """
        Tests that when stock drops to or below reorder_level, notifications are generated.
        """
        # Drop chicken stock from 10kg to 4kg (below reorder_level of 8kg)
        self.client.post('/api/v1/stock/remove/', {
            'item_id': str(self.chicken.id),
            'quantity': '6.000'
        })
        self.chicken.refresh_from_db()
        self.assertTrue(self.chicken.reorder_needed)

        # Trigger check-alerts API
        res_scan = self.client.post('/api/v1/stock/check-alerts/')
        self.assertEqual(res_scan.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(res_scan.data['alertsGenerated'], 1)

        # Verify notification was stored
        notifs = Notification.objects.filter(notification_type=Notification.NotificationType.LOW_INVENTORY)
        self.assertTrue(notifs.exists())

    def test_inventory_valuation(self):
        """
        Tests GET /api/v1/stock/valuation/
        """
        res = self.client.get('/api/v1/stock/valuation/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data

        self.assertIn('totalValuation', data)
        self.assertIn('categoryBreakdown', data)
        self.assertIn('highValueItems', data)
        self.assertIn('estimatedReplenishmentCost', data)

    def test_supplier_management_and_products_supplied(self):
        """
        Tests GET /api/v1/stock/suppliers/<id>/ displays supplier info,
        products supplied with purchase prices, and order history.
        """
        res = self.client.get(f'/api/v1/stock/suppliers/{self.supplier.id}/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data

        self.assertEqual(data['name'], 'Dublin Meats & Poultry Ltd')
        self.assertIn('productsSupplied', data)
        self.assertEqual(len(data['productsSupplied']), 1)
        self.assertEqual(data['productsSupplied'][0]['name'], 'Fresh Chicken Fillet')
        self.assertEqual(data['productsSupplied'][0]['purchasePrice'], 6.5)

    def test_purchase_order_workflow_and_delivery_receiving(self):
        """
        Tests creating a Purchase Order and recording incoming delivery.
        """
        # 1. Create PO for 20kg Chicken
        po_payload = {
            'supplier': str(self.supplier.id),
            'expected_delivery_date': (timezone.now() + timedelta(days=2)).date().isoformat(),
            'notes': 'Deliver before 11:00 AM',
            'items': [
                {
                    'inventory_item_id': str(self.chicken.id),
                    'quantity_ordered': '20.000',
                    'unit_cost': '6.50',
                    'unit': 'kg'
                }
            ]
        }
        res_po = self.client.post('/api/v1/stock/purchase-orders/', po_payload, format='json')
        self.assertEqual(res_po.status_code, status.HTTP_201_CREATED)
        po_id = res_po.data['id']
        po_item_id = res_po.data['items'][0]['id']

        # Initial Chicken stock was 10kg
        self.assertEqual(self.chicken.current_stock, Decimal('10.000'))

        # 2. Receive incoming delivery of 20kg
        res_receive = self.client.post(f'/api/v1/stock/purchase-orders/{po_id}/receive/', {
            'invoice_number': 'INV-DUB-9988',
            'received_items': [
                {
                    'item_id': po_item_id,
                    'quantity_received': '20.000',
                    'batch_number': 'BATCH-002',
                    'expiry_date': (timezone.now() + timedelta(days=5)).date().isoformat()
                }
            ]
        }, format='json')

        self.assertEqual(res_receive.status_code, status.HTTP_200_OK)
        # Verify Chicken stock incremented to 30kg
        self.chicken.refresh_from_db()
        self.assertEqual(self.chicken.current_stock, Decimal('30.000'))
        # Verify PO status updated to RECEIVED
        po = PurchaseOrder.objects.get(id=po_id)
        self.assertEqual(po.status, PurchaseOrder.Status.RECEIVED)
        self.assertEqual(po.invoice_number, 'INV-DUB-9988')

    def test_stock_transfers_and_audit_reconciliation(self):
        """
        Tests location transfer and manual physical audit reconciliation.
        """
        # Transfer 5kg from Main Storage to Line 1 Prep Table
        res_trans = self.client.post('/api/v1/stock/transfers/', {
            'from_location': 'Main Walk-in Cooler',
            'to_location': 'Line 1 Prep Table',
            'items': [
                {'inventory_item_id': str(self.chicken.id), 'quantity': '5.000', 'unit': 'kg'}
            ]
        }, format='json')
        self.assertEqual(res_trans.status_code, status.HTTP_201_CREATED)

        # Audit Count Session
        res_audit = self.client.post('/api/v1/stock/audits/', {
            'name': 'Weekly Stock Audit',
            'items': [
                {
                    'inventory_item_id': str(self.chicken.id),
                    'expected_stock': '10.000',
                    'actual_stock': '9.000'  # 1kg missing
                }
            ]
        }, format='json')
        self.assertEqual(res_audit.status_code, status.HTTP_201_CREATED)
        audit_id = res_audit.data['id']

        # 1-Click Reconcile
        res_rec = self.client.post(f'/api/v1/stock/audits/{audit_id}/reconcile/')
        self.assertEqual(res_rec.status_code, status.HTTP_200_OK)
        self.chicken.refresh_from_db()
        # Stock updated to counted actual (9kg)
        self.assertEqual(self.chicken.current_stock, Decimal('9.000'))

    def test_food_cost_and_profitability_dashboard(self):
        """
        Tests GET /api/v1/stock/profitability/
        Identifies:
        - Ingredient cost, Selling price, Gross margin, Food cost %
        - Most profitable products
        - Least profitable products
        - Best sellers
        - Slow-moving products
        - High-cost ingredients
        """
        res = self.client.get('/api/v1/stock/profitability/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data

        self.assertIn('mostProfitableProducts', data)
        self.assertIn('leastProfitableProducts', data)
        self.assertIn('bestSellers', data)
        self.assertIn('slowMovingProducts', data)
        self.assertIn('highCostIngredients', data)

        # Best seller should be Chicken Tikka Masala (120 orders)
        self.assertEqual(data['bestSellers'][0]['name'], 'Chicken Tikka Masala')

        # Slow moving should be Exotic Saffron Prawn (5 orders)
        self.assertEqual(data['slowMovingProducts'][0]['name'], 'Exotic Saffron Prawn')

        # High cost ingredient should be Pure Spanish Saffron (€12.00/g)
        self.assertEqual(data['highCostIngredients'][0]['name'], 'Pure Spanish Saffron')
        self.assertEqual(data['highCostIngredients'][0]['purchasePrice'], 12.0)

