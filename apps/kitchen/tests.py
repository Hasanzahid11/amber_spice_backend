from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import RolePermissionConfig
from apps.menu.models import Category, Dish
from apps.orders.models import Order, OrderItem
from .models import KitchenStation, KitchenScreen, KitchenBumpLog

User = get_user_model()


class KitchenDisplaySystemTests(APITestCase):
    """
    Comprehensive test suite for the Kitchen Display System (KDS).
    Tests screen display metrics, lifecycle (New -> Preparing -> Ready),
    delay detection, station filtering, item ticking, and audit logs.
    """

    def setUp(self):
        # Create Kitchen Staff User
        self.kitchen_user = User.objects.create_user(
            username='chef_gordon',
            email='chef@amberspice.com',
            phone='+353871112233',
            password='SecretPassword123!',
            role=User.Role.KITCHEN_STAFF,
            first_name='Gordon',
            last_name='Ramsay'
        )

        # Create Manager User
        self.manager_user = User.objects.create_user(
            username='manager_alice',
            email='alice@amberspice.com',
            phone='+353874445566',
            password='SecretPassword123!',
            role=User.Role.MANAGER,
            first_name='Alice',
            last_name='Manager'
        )

        # Authenticate as kitchen staff by default
        self.client.force_authenticate(user=self.kitchen_user)

        # Create Stations
        self.curry_station = KitchenStation.objects.create(
            name='Curry Station',
            slug='curry',
            color_code='#E65100',
            display_order=1
        )
        self.grill_station = KitchenStation.objects.create(
            name='Grill Station',
            slug='grill',
            color_code='#D32F2F',
            display_order=2
        )

        # Create Menu Category & Dishes
        self.category = Category.objects.create(name='Main Dishes', slug='main-dishes')
        self.curry_dish = Dish.objects.create(
            category=self.category,
            name='Chicken Tikka Masala',
            price=Decimal('15.50'),
            station='curry'
        )
        self.grill_dish = Dish.objects.create(
            category=self.category,
            name='Seekh Kebab',
            price=Decimal('12.00'),
            station='grill'
        )

        # Create Sample Orders
        # Order 1: New / Pending ASAP Dine-in
        self.order1 = Order.objects.create(
            customer_name='John Doe',
            customer_phone='+353871234567',
            dining_type=Order.DiningType.DINE_IN,
            table_number='T4',
            status=Order.Status.PENDING,
            priority=Order.Priority.NORMAL,
            estimated_time_minutes=20,
            notes='Allergy: No Peanuts'
        )
        self.item1 = OrderItem.objects.create(
            order=self.order1,
            dish=self.curry_dish,
            name='Chicken Tikka Masala',
            quantity=2,
            price=Decimal('15.50'),
            station='curry',
            customizations={
                'portion': 'Large',
                'extras': ['Extra Gravy'],
                'modifiers': {'spice_level': 'Medium'},
                'removed_ingredients': ['Peanuts'],
                'added_ingredients': ['Extra Cream']
            },
            special_instructions='Mild spice for the children'
        )

        # Order 2: Preparing Takeaway with Urgent Priority
        self.order2 = Order.objects.create(
            customer_name='Sarah Smith',
            customer_phone='+353879876543',
            dining_type=Order.DiningType.TAKEAWAY,
            status=Order.Status.PREPARING,
            priority=Order.Priority.URGENT,
            estimated_time_minutes=15,
            prepared_at=timezone.now()
        )
        self.item2 = OrderItem.objects.create(
            order=self.order2,
            dish=self.grill_dish,
            name='Seekh Kebab',
            quantity=1,
            price=Decimal('12.00'),
            station='grill',
            customizations={'portion': 'Regular'},
            special_instructions='Extra lemon wedges'
        )

    def test_kds_screen_display_order_attributes(self):
        """
        Tests that incoming tickets display all required attributes:
        order number, items, portion, modifiers/extras, special instructions,
        order type, required time, elapsed time, priority.
        """
        response = self.client.get('/api/v1/kitchen/tickets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 2)

        # Urgent order (order2) should appear first in queue
        first_ticket = response.data[0]
        self.assertEqual(first_ticket['orderNumber'], self.order2.order_number)
        self.assertEqual(first_ticket['priority'], 'urgent')
        self.assertEqual(first_ticket['diningType'], 'takeaway')

        # Check order1 details
        second_ticket = [t for t in response.data if t['orderNumber'] == self.order1.order_number][0]
        self.assertEqual(second_ticket['status'], 'pending')
        self.assertEqual(second_ticket['diningType'], 'dine_in')
        self.assertEqual(second_ticket['tableNumber'], 'T4')
        self.assertEqual(second_ticket['priority'], 'normal')
        self.assertEqual(second_ticket['estimatedTimeMinutes'], 20)
        self.assertIn('elapsedMinutes', second_ticket)
        self.assertIn('timeRemainingMinutes', second_ticket)
        self.assertIn('targetCompletionTime', second_ticket)
        self.assertFalse(second_ticket['isDelayed'])
        self.assertEqual(second_ticket['delaySeverity'], 'on_time')

        # Check detailed items display
        items = second_ticket['items']
        self.assertEqual(len(items), 1)
        item_data = items[0]
        self.assertEqual(item_data['name'], 'Chicken Tikka Masala')
        self.assertEqual(item_data['portion'], 'Large')
        self.assertEqual(item_data['extras'], ['Extra Gravy'])
        self.assertEqual(item_data['removedIngredients'], ['Peanuts'])
        self.assertEqual(item_data['addedIngredients'], ['Extra Cream'])
        self.assertEqual(item_data['specialInstructions'], 'Mild spice for the children')
        self.assertFalse(item_data['isReady'])

    def test_kds_status_progression_new_preparing_ready(self):
        """
        Tests the 1-click bump progression:
        New (pending) -> Preparing -> Ready.
        """
        # Step 1: Bump from PENDING to PREPARING
        bump1_res = self.client.post(f'/api/v1/kitchen/tickets/{self.order1.id}/bump/')
        self.assertEqual(bump1_res.status_code, status.HTTP_200_OK)
        self.order1.refresh_from_db()
        self.assertEqual(self.order1.status, Order.Status.PREPARING)
        self.assertIsNotNone(self.order1.prepared_at)

        # Verify audit log was created
        log1 = KitchenBumpLog.objects.filter(order=self.order1, action=KitchenBumpLog.Action.START_PREP).first()
        self.assertIsNotNone(log1)
        self.assertEqual(log1.performed_by, self.kitchen_user)

        # Step 2: Bump from PREPARING to READY
        bump2_res = self.client.post(f'/api/v1/kitchen/tickets/{self.order1.id}/bump/')
        self.assertEqual(bump2_res.status_code, status.HTTP_200_OK)
        self.order1.refresh_from_db()
        self.assertEqual(self.order1.status, Order.Status.READY)
        self.assertIsNotNone(self.order1.ready_at)

        # Verify all items marked ready
        self.item1.refresh_from_db()
        self.assertTrue(self.item1.is_ready)

        # Verify ready audit log
        log2 = KitchenBumpLog.objects.filter(order=self.order1, action=KitchenBumpLog.Action.MARK_READY).first()
        self.assertIsNotNone(log2)

    def test_kds_recall_order(self):
        """
        Tests recalling an order from READY back to PREPARING if bumped by mistake.
        """
        self.order2.status = Order.Status.READY
        self.order2.ready_at = timezone.now()
        self.order2.save()

        recall_res = self.client.post(f'/api/v1/kitchen/tickets/{self.order2.id}/recall/', {
            'reason': 'Extra naan bread added to order'
        })
        self.assertEqual(recall_res.status_code, status.HTTP_200_OK)
        self.order2.refresh_from_db()
        self.assertEqual(self.order2.status, Order.Status.PREPARING)
        self.assertIsNone(self.order2.ready_at)

        # Check recall audit log
        recall_log = KitchenBumpLog.objects.filter(order=self.order2, action=KitchenBumpLog.Action.RECALL).first()
        self.assertIsNotNone(recall_log)

    def test_kds_station_filtering(self):
        """
        Tests that station cooks can filter orders and items to their specific station.
        """
        # Curry Station screen
        curry_res = self.client.get('/api/v1/kitchen/tickets/?station=curry')
        self.assertEqual(curry_res.status_code, status.HTTP_200_OK)
        order_numbers = [t['orderNumber'] for t in curry_res.data]
        self.assertIn(self.order1.order_number, order_numbers)
        self.assertNotIn(self.order2.order_number, order_numbers)

        # Grill Station screen
        grill_res = self.client.get('/api/v1/kitchen/tickets/?station=grill')
        self.assertEqual(grill_res.status_code, status.HTTP_200_OK)
        order_numbers_grill = [t['orderNumber'] for t in grill_res.data]
        self.assertIn(self.order2.order_number, order_numbers_grill)
        self.assertNotIn(self.order1.order_number, order_numbers_grill)

    def test_kds_item_completion_toggle(self):
        """
        Tests station cook checking off an individual item as ready.
        """
        self.assertFalse(self.item1.is_ready)

        toggle_res = self.client.post(f'/api/v1/kitchen/tickets/{self.order1.id}/toggle-item/', {
            'item_id': str(self.item1.id)
        })
        self.assertEqual(toggle_res.status_code, status.HTTP_200_OK)
        self.item1.refresh_from_db()
        self.assertTrue(self.item1.is_ready)
        self.assertTrue(toggle_res.data['isReady'])
        self.assertTrue(toggle_res.data['allReady'])

    def test_kds_delayed_orders_identification(self):
        """
        Tests delayed order metrics and severity calculation:
        on_time -> warning -> delayed -> critical.
        """
        # Create a delayed order created 40 minutes ago with 20 min estimated prep time
        delayed_order = Order.objects.create(
            customer_name='Delayed Customer',
            customer_phone='+353870009988',
            dining_type=Order.DiningType.DELIVERY,
            status=Order.Status.PREPARING,
            estimated_time_minutes=20,
            priority=Order.Priority.NORMAL
        )
        # Mock created_at to 40 minutes ago
        Order.objects.filter(id=delayed_order.id).update(
            created_at=timezone.now() - timedelta(minutes=40)
        )
        delayed_order.refresh_from_db()

        self.assertTrue(delayed_order.is_delayed)
        self.assertGreaterEqual(delayed_order.delay_minutes, 19)
        self.assertEqual(delayed_order.delay_severity, 'critical')

        # Filter by delayed_only=true
        res = self.client.get('/api/v1/kitchen/tickets/?delayed_only=true')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        delayed_numbers = [t['orderNumber'] for t in res.data]
        self.assertIn(delayed_order.order_number, delayed_numbers)
        self.assertNotIn(self.order1.order_number, delayed_numbers)

    def test_kds_summary_metrics(self):
        """
        Tests the /api/v1/kitchen/summary/ header metrics endpoint.
        """
        res = self.client.get('/api/v1/kitchen/summary/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('totalActiveOrders', res.data)
        self.assertIn('newOrdersCount', res.data)
        self.assertIn('preparingOrdersCount', res.data)
        self.assertIn('readyOrdersCount', res.data)
        self.assertIn('delayedOrdersCount', res.data)
        self.assertIn('urgentPriorityCount', res.data)
        self.assertEqual(res.data['urgentPriorityCount'], 1)  # order2 is urgent

