from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.menu.models import Category, Dish
from apps.orders.models import Order, OrderItem
from .models import (
    InventoryItem,
    Recipe,
    RecipeIngredient,
    StockMovement,
    Supplier,
)
from .utils import convert_quantity, normalize_unit

User = get_user_model()


class InventoryManagementTests(APITestCase):
    def setUp(self):
        # 1. Staff users
        self.manager = User.objects.create_user(
            username='inventory_manager',
            email='manager@restaurant.com',
            phone='+353875551009',
            password='password123',
            role=User.Role.MANAGER
        )
        self.kitchen_staff = User.objects.create_user(
            username='chef_raj',
            email='chef@restaurant.com',
            phone='+353875551010',
            password='password123',
            role=User.Role.KITCHEN_STAFF
        )
        self.customer = User.objects.create_user(
            username='customer_jane',
            email='jane@example.com',
            phone='+353871234567',
            password='password123',
            role=User.Role.CUSTOMER
        )

        # 2. Supplier
        self.supplier = Supplier.objects.create(
            name='Celtic Quality Meats & Produce',
            contact_name='Liam O’Connor',
            phone='+3531234567',
            email='orders@celticmeats.ie'
        )

        # 3. Standard Ingredients (Chicken, Rice, Sauce, etc.)
        self.chicken = InventoryItem.objects.create(
            name='Fresh Chicken Breast',
            category=InventoryItem.Category.MEAT_POULTRY,
            current_stock=Decimal('20.000'),
            minimum_stock=Decimal('5.000'),
            reorder_level=Decimal('8.000'),
            unit='kg',
            purchase_price=Decimal('6.50'),
            supplier_ref=self.supplier,
            expiry_date=date.today() + timedelta(days=5),
            batch_number='BATCH-CHK-202611'
        )
        self.rice = InventoryItem.objects.create(
            name='Aromatic Basmati Rice',
            category=InventoryItem.Category.RICE_GRAINS,
            current_stock=Decimal('50.000'),
            minimum_stock=Decimal('10.000'),
            reorder_level=Decimal('15.000'),
            unit='kg',
            purchase_price=Decimal('2.20'),
            supplier='Himalayan Spices & Grains'
        )
        self.sauce = InventoryItem.objects.create(
            name='Signature Biryani Curry Sauce',
            category=InventoryItem.Category.SAUCES,
            current_stock=Decimal('10.000'),
            minimum_stock=Decimal('2.000'),
            reorder_level=Decimal('3.000'),
            unit='kg',
            purchase_price=Decimal('4.80')
        )

        # 4. Menu Dish & Category
        self.menu_cat = Category.objects.create(name='Biryani Specialties', slug='biryani-specialties')
        self.dish = Dish.objects.create(
            category=self.menu_cat,
            name='Amber Royal Chicken Biryani',
            slug='amber-royal-chicken-biryani',
            price=Decimal('16.50')
        )

        # 5. Recipe / BOM for Dish: 200g chicken, 100g rice, 20g sauce per portion
        self.recipe = Recipe.objects.create(
            dish=self.dish,
            name='Amber Royal Chicken Biryani Recipe',
            yield_portions=1,
            prep_time_minutes=20
        )
        RecipeIngredient.objects.create(
            recipe=self.recipe,
            inventory_item=self.chicken,
            quantity=Decimal('200.000'),
            unit='g'
        )
        RecipeIngredient.objects.create(
            recipe=self.recipe,
            inventory_item=self.rice,
            quantity=Decimal('100.000'),
            unit='g'
        )
        RecipeIngredient.objects.create(
            recipe=self.recipe,
            inventory_item=self.sauce,
            quantity=Decimal('20.000'),
            unit='g'
        )

    def test_unit_conversion_utility(self):
        # 200 grams to kg
        qty_kg = convert_quantity(Decimal('200.000'), 'g', 'kg')
        self.assertEqual(qty_kg, Decimal('0.200'))

        # 1.5 kg to grams
        qty_g = convert_quantity(Decimal('1.500'), 'kg', 'g')
        self.assertEqual(qty_g, Decimal('1500.000'))

        # 250 ml to litres
        qty_l = convert_quantity(Decimal('250.000'), 'ml', 'litre')
        self.assertEqual(qty_l, Decimal('0.250'))

        # Incompatible units remain unchanged
        qty_pcs = convert_quantity(Decimal('4'), 'pieces', 'kg')
        self.assertEqual(qty_pcs, Decimal('4'))

    def test_create_inventory_items_all_categories(self):
        self.client.force_authenticate(user=self.manager)

        items_to_test = [
            ('Prime Irish Beef Mince', InventoryItem.Category.BEEF_LAMB, 'kg', Decimal('12.50')),
            ('Chakki Atta Wheat Flour', InventoryItem.Category.FLOUR_BAKERY, 'kg', Decimal('1.80')),
            ('Pure Mustard & Sunflower Oil', InventoryItem.Category.OILS_FATS, 'litre', Decimal('3.20')),
            ('Fresh Red Onions & Coriander', InventoryItem.Category.VEGETABLES, 'kg', Decimal('1.50')),
            ('Tandoori Masala & Turmeric Spices', InventoryItem.Category.SPICES_SEASONING, 'kg', Decimal('15.00')),
            ('Mango Lassi & Soft Drinks', InventoryItem.Category.DRINKS, 'pieces', Decimal('1.10')),
            ('Eco Kraft Takeaway Containers', InventoryItem.Category.PACKAGING, 'pieces', Decimal('0.25')),
            ('Kitchen Cleaning & Sanitizer Rolls', InventoryItem.Category.OTHER, 'packs', Decimal('8.50')),
        ]

        for name, category, unit, price in items_to_test:
            payload = {
                'name': name,
                'category': category,
                'currentStock': 100,
                'minimumStock': 20,
                'reorderLevel': 30,
                'unit': unit,
                'purchasePrice': float(price),
                'storageLocation': 'Main Dry Store',
                'batchNumber': 'LOT-2026-X'
            }
            res = self.client.post('/api/v1/inventory/items/', payload, format='json')
            self.assertEqual(res.status_code, status.HTTP_201_CREATED)
            self.assertEqual(res.data['name'], name)
            self.assertEqual(res.data['category'], category)
            self.assertEqual(res.data['unit'], unit)
            self.assertEqual(float(res.data['purchasePrice']), float(price))

    def test_recipe_bom_food_costing(self):
        # Recipe food cost calculation:
        # Chicken: 200g @ €6.50/kg = 0.200 * 6.50 = €1.30
        # Rice:    100g @ €2.20/kg = 0.100 * 2.20 = €0.22
        # Sauce:    20g @ €4.80/kg = 0.020 * 4.80 = €0.096 -> €0.10
        # Total cost: 1.30 + 0.22 + 0.10 = €1.62
        self.assertAlmostEqual(float(self.recipe.total_cost), 1.62, places=2)
        self.assertAlmostEqual(float(self.recipe.cost_per_portion), 1.62, places=2)
        # Dish sells for €16.50 -> Food cost % = (1.62 / 16.50) * 100 ~= 9.82%
        self.assertAlmostEqual(self.recipe.food_cost_percentage, 9.82, places=1)

    def test_calculate_consumption_api_10_portions(self):
        """
        User scenario:
        Customer orders 10 portions of a dish that uses:
        - 200 g chicken
        - 100 g rice
        - 20 g sauce
        Calculates ingredient consumption:
        Chicken: 2000g (2.000 kg)
        Rice: 1000g (1.000 kg)
        Sauce: 200g (0.200 kg)
        """
        self.client.force_authenticate(user=self.kitchen_staff)

        payload = {
            'items': [
                {'dish_id': self.dish.id, 'quantity': 10}
            ]
        }
        res = self.client.post('/api/v1/inventory/calculate-consumption/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['can_fulfill'])

        consumed = {c['name']: c for c in res.data['consumed_ingredients']}

        # Check Chicken
        chk = consumed['Fresh Chicken Breast']
        self.assertAlmostEqual(chk['quantity_consumed'], 2.000, places=3)
        self.assertAlmostEqual(chk['current_stock'], 20.000, places=3)
        self.assertAlmostEqual(chk['projected_remaining_stock'], 18.000, places=3)

        # Check Rice
        rc = consumed['Aromatic Basmati Rice']
        self.assertAlmostEqual(rc['quantity_consumed'], 1.000, places=3)
        self.assertAlmostEqual(rc['current_stock'], 50.000, places=3)
        self.assertAlmostEqual(rc['projected_remaining_stock'], 49.000, places=3)

        # Check Sauce
        sc = consumed['Signature Biryani Curry Sauce']
        self.assertAlmostEqual(sc['quantity_consumed'], 0.200, places=3)
        self.assertAlmostEqual(sc['current_stock'], 10.000, places=3)
        self.assertAlmostEqual(sc['projected_remaining_stock'], 9.800, places=3)

    def test_order_inventory_deduction_and_movement_logs(self):
        # 1. Create order for 10 portions of Chicken Biryani
        order = Order.objects.create(
            customer=self.customer,
            customer_name='Jane Doe',
            customer_phone='+353871234567',
            dining_type=Order.DiningType.DELIVERY,
            status=Order.Status.PENDING,
            total_amount=Decimal('165.00')
        )
        OrderItem.objects.create(
            order=order,
            dish=self.dish,
            name=self.dish.name,
            quantity=10,
            price=self.dish.price
        )

        self.client.force_authenticate(user=self.kitchen_staff)

        # 2. Kitchen marks order as PREPARING -> Auto-deducts inventory
        res_status = self.client.post(f'/api/v1/orders/{order.id}/update_status/', {'status': 'preparing'}, format='json')
        self.assertEqual(res_status.status_code, status.HTTP_200_OK)

        # 3. Verify physical inventory deductions in database
        self.chicken.refresh_from_db()
        self.rice.refresh_from_db()
        self.sauce.refresh_from_db()

        self.assertAlmostEqual(float(self.chicken.current_stock), 18.000, places=3)
        self.assertAlmostEqual(float(self.rice.current_stock), 49.000, places=3)
        self.assertAlmostEqual(float(self.sauce.current_stock), 9.800, places=3)

        # 4. Verify StockMovement logs created
        movements = StockMovement.objects.filter(order=order)
        self.assertEqual(movements.count(), 3)
        chk_mov = movements.filter(inventory_item=self.chicken).first()
        self.assertAlmostEqual(float(chk_mov.quantity), -2.000, places=3)
        self.assertEqual(chk_mov.movement_type, StockMovement.MovementType.CONSUMPTION)

        # 5. Idempotency test: calling deduct again does not double-deduct
        res_repeat = self.client.post(f'/api/v1/orders/{order.id}/deduct-inventory/')
        self.assertEqual(res_repeat.status_code, status.HTTP_200_OK)
        self.chicken.refresh_from_db()
        self.assertAlmostEqual(float(self.chicken.current_stock), 18.000, places=3)

    def test_restock_action_api(self):
        self.client.force_authenticate(user=self.manager)

        restock_url = f'/api/v1/inventory/items/{self.chicken.id}/restock/'
        payload = {
            'quantity': 15.000,
            'purchasePrice': 6.20,
            'batchNumber': 'BATCH-NOV-15',
            'notes': 'Weekly wholesale chicken breast delivery'
        }
        res = self.client.post(restock_url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.chicken.refresh_from_db()
        # 20.000 + 15.000 = 35.000
        self.assertAlmostEqual(float(self.chicken.current_stock), 35.000, places=3)
        self.assertAlmostEqual(float(self.chicken.purchase_price), 6.20, places=2)
        self.assertEqual(self.chicken.batch_number, 'BATCH-NOV-15')

    def test_waste_action_api(self):
        self.client.force_authenticate(user=self.manager)

        waste_url = f'/api/v1/inventory/items/{self.chicken.id}/waste/'
        payload = {
            'quantity': 1.500,
            'reason': 'Damaged package dropped during prep'
        }
        res = self.client.post(waste_url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.chicken.refresh_from_db()
        # 20.000 - 1.500 = 18.500
        self.assertAlmostEqual(float(self.chicken.current_stock), 18.500, places=3)

        waste_mov = StockMovement.objects.filter(inventory_item=self.chicken, movement_type=StockMovement.MovementType.WASTE).first()
        self.assertIsNotNone(waste_mov)
        self.assertAlmostEqual(float(waste_mov.quantity), -1.500, places=3)

    def test_low_stock_and_reorder_alert_endpoints(self):
        self.client.force_authenticate(user=self.kitchen_staff)

        # Drop chicken stock below minimum (minimum is 5.0, current 20.0)
        self.chicken.current_stock = Decimal('4.000')
        self.chicken.save(update_fields=['current_stock'])

        # Test both /items/low_stock/ and alias /low-stock/
        res1 = self.client.get('/api/v1/inventory/items/low_stock/')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        item_names = [i['name'] for i in res1.data]
        self.assertIn('Fresh Chicken Breast', item_names)

        res2 = self.client.get('/api/v1/inventory/low-stock/')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        item_names_alias = [i['name'] for i in res2.data]
        self.assertIn('Fresh Chicken Breast', item_names_alias)

        # Test reorder alerts
        res_reorder = self.client.get('/api/v1/inventory/items/reorder-alerts/')
        self.assertEqual(res_reorder.status_code, status.HTTP_200_OK)
        reorder_names = [i['name'] for i in res_reorder.data]
        self.assertIn('Fresh Chicken Breast', reorder_names)

    def test_supplier_crud_api(self):
        self.client.force_authenticate(user=self.manager)

        res_list = self.client.get('/api/v1/inventory/suppliers/')
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res_list.data), 1)

        payload = {
            'name': 'Dublin Spice & Herb Importers',
            'contactName': 'Sean Higgins',
            'email': 'sean@dublinspices.ie',
            'phone': '+353871112233',
            'leadTimeDays': 1
        }
        res_create = self.client.post('/api/v1/inventory/suppliers/', payload, format='json')
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_create.data['name'], 'Dublin Spice & Herb Importers')
        self.assertEqual(res_create.data['contactName'], 'Sean Higgins')
