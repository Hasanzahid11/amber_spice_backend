from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.menu.models import Category as MenuCategory, Dish
from apps.orders.models import Order, OrderItem
from ..models import InventoryCategory, InventoryItem, DishRecipe, StockTransaction, StockAlert
from ..services import deplete_order_inventory, restore_order_inventory, calculate_dish_cost_data

User = get_user_model()


class RecipeAndDepletionTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username='recipe-manager',
            email='recipe-manager@example.com',
            role=User.Role.MANAGER,
        )
        cls.staff = User.objects.create_user(
            username='recipe-staff',
            email='recipe-staff@example.com',
            role=User.Role.STAFF,
        )

        cls.inv_cat = InventoryCategory.objects.create(name='Fresh Ingredients')
        cls.chicken = InventoryItem.objects.create(
            name='Chicken Breast',
            category='Meat & Poultry',
            category_ref=cls.inv_cat,
            current_stock=Decimal('10.000'),
            minimum_stock=Decimal('2.000'),
            cost_per_unit=Decimal('8.5000'),  # 8.50 / kg
            unit='kg',
        )
        cls.basmati = InventoryItem.objects.create(
            name='Basmati Rice',
            category='Pantry',
            category_ref=cls.inv_cat,
            current_stock=Decimal('25.000'),
            minimum_stock=Decimal('5.000'),
            cost_per_unit=Decimal('2.2000'),  # 2.20 / kg
            unit='kg',
        )
        cls.ghee = InventoryItem.objects.create(
            name='Pure Desi Ghee',
            category='Dairy',
            category_ref=cls.inv_cat,
            current_stock=Decimal('5.000'),
            minimum_stock=Decimal('1.000'),
            cost_per_unit=Decimal('12.0000'),  # 12.00 / kg
            unit='kg',
        )

        cls.menu_cat = MenuCategory.objects.create(name='Biryani Specialties', slug='biryani-specialties')
        cls.dish = Dish.objects.create(
            category=cls.menu_cat,
            name='Amber Dum Biryani',
            price=Decimal('15.50'),
            is_available=True,
        )

        # Recipe: 0.250kg chicken (2.125), 0.200kg rice (0.44), 0.030kg ghee (0.36) -> Total Cost = 2.925 (~2.93)
        cls.r1 = DishRecipe.objects.create(dish=cls.dish, ingredient=cls.chicken, quantity=Decimal('0.250'), unit='kg')
        cls.r2 = DishRecipe.objects.create(dish=cls.dish, ingredient=cls.basmati, quantity=Decimal('0.200'), unit='kg')
        cls.r3 = DishRecipe.objects.create(dish=cls.dish, ingredient=cls.ghee, quantity=Decimal('0.030'), unit='kg')

    def test_recipe_cost_calculation(self):
        data = calculate_dish_cost_data(self.dish)
        # Chicken: 0.250 * 8.50 = 2.125 -> quantize 2.12
        # Rice: 0.200 * 2.20 = 0.440
        # Ghee: 0.030 * 12.00 = 0.360
        # Total = 2.12 + 0.44 + 0.36 = 2.92
        self.assertEqual(data['total_food_cost'], Decimal('2.92'))
        # Dish price: 15.50
        # Food cost % = 2.92 / 15.50 * 100 = 18.84%
        self.assertAlmostEqual(float(data['food_cost_percent']), 18.84, places=1)
        # Gross profit: 15.50 - 2.92 = 12.58
        self.assertEqual(data['gross_profit'], Decimal('12.58'))
        # Max portions: chicken has 10kg / 0.25 = 40; rice 25 / 0.2 = 125; ghee 5 / 0.03 = 166 -> min is 40
        self.assertEqual(data['max_portions_available'], 40)

    def test_cost_summary_endpoint(self):
        self.client.force_authenticate(user=self.staff)
        url = reverse('dish-recipe-cost-summary')
        response = self.client.get(url, {'dish': self.dish.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        summary = response.data[0]
        self.assertEqual(summary['dishId'], self.dish.id)
        self.assertEqual(summary['dishName'], 'Amber Dum Biryani')
        self.assertEqual(Decimal(str(summary['totalFoodCost'])), Decimal('2.92'))
        self.assertEqual(summary['maxPortionsAvailable'], 40)

    def test_auto_depletion_and_audit_transaction(self):
        order = Order.objects.create(
            customer_name='John Doe',
            total_amount=Decimal('31.00'),
            dining_type=Order.DiningType.TAKEAWAY,
            status=Order.Status.PENDING,
        )
        OrderItem.objects.create(
            order=order,
            dish=self.dish,
            name=self.dish.name,
            quantity=2,
            price=self.dish.price,
        )

        transactions = deplete_order_inventory(order, user=self.manager)
        self.assertEqual(len(transactions), 3)

        self.chicken.refresh_from_db()
        self.basmati.refresh_from_db()
        self.ghee.refresh_from_db()

        # 2 portions: chicken -0.500 kg (10.000 -> 9.500)
        self.assertEqual(self.chicken.current_stock, Decimal('9.50'))
        # rice -0.400 kg (25.000 -> 24.600)
        self.assertEqual(self.basmati.current_stock, Decimal('24.60'))
        # ghee -0.060 kg (5.000 -> 4.940)
        self.assertEqual(self.ghee.current_stock, Decimal('4.94'))

        # Check StockTransaction audit log
        tx = StockTransaction.objects.filter(order=order, item=self.chicken).first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.transaction_type, StockTransaction.TransactionType.CONSUMPTION)
        self.assertEqual(tx.quantity_delta, Decimal('-0.500'))
        self.assertEqual(tx.unit_cost, Decimal('8.5000'))
        self.assertEqual(tx.total_cost, Decimal('4.25'))
        self.assertEqual(tx.balance_after, Decimal('9.50'))

        # Test idempotency: calling deplete_order_inventory again does not double-deduct
        tx_repeat = deplete_order_inventory(order, user=self.manager)
        self.assertEqual(len(tx_repeat), 0)
        self.chicken.refresh_from_db()
        self.assertEqual(self.chicken.current_stock, Decimal('9.50'))

    def test_restore_on_order_cancellation(self):
        order = Order.objects.create(
            customer_name='Jane Doe',
            total_amount=Decimal('15.50'),
            dining_type=Order.DiningType.DINE_IN,
            status=Order.Status.PENDING,
        )
        OrderItem.objects.create(
            order=order,
            dish=self.dish,
            name=self.dish.name,
            quantity=1,
            price=self.dish.price,
        )

        deplete_order_inventory(order, user=self.manager)
        self.chicken.refresh_from_db()
        self.assertEqual(self.chicken.current_stock, Decimal('9.75'))

        # Cancel and restore
        restored = restore_order_inventory(order, user=self.manager)
        self.assertEqual(len(restored), 3)

        self.chicken.refresh_from_db()
        self.assertEqual(self.chicken.current_stock, Decimal('10.00'))

    def test_manual_stock_adjustment_api(self):
        self.client.force_authenticate(user=self.manager)
        url = reverse('stock-transaction-adjust')
        payload = {
            'item': self.chicken.pk,
            'transactionType': 'PURCHASE',
            'quantityDelta': '5.000',
            'unitCost': '8.2000',
            'notes': 'Fresh morning delivery invoice #1042',
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.chicken.refresh_from_db()
        self.assertEqual(self.chicken.current_stock, Decimal('15.00'))
        self.assertEqual(self.chicken.cost_per_unit, Decimal('8.2000'))
