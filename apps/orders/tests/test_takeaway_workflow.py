from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from apps.menu.models import Category, Dish
from apps.orders.models import Order

User = get_user_model()


class TakeawayWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Admin user
        self.admin = User.objects.create_user(
            username='admin_user',
            email='admin@test.com',
            password='Password123!',
            role=User.Role.ADMIN,
            is_staff=True,
        )

        # Menu Category and Dish
        self.category = Category.objects.create(name='Biryani', slug='biryani')
        self.dish = Dish.objects.create(
            name='Royal Chicken Dum Biryani',
            category=self.category,
            price=Decimal('15.00'),
            is_available=True,
            station='biryani',
        )

    def test_takeaway_creation_generates_pickup_code(self):
        """Takeaway order generates a short pickup code and succeeds without address."""
        payload = {
            'customerName': 'Tanvir Rahman',
            'customerPhone': '+353871234567',
            'diningType': 'takeaway',
            'paymentMethod': 'cash',
            'notes': 'Pack sauce separately',
            'items': [{'dishId': self.dish.id, 'quantity': 2}],
        }
        res = self.client.post('/api/v1/orders/', payload, format='json')
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data['diningType'], 'takeaway')
        self.assertTrue(data['pickupCode'].startswith('TK-'))
        self.assertEqual(data['customerName'], 'Tanvir Rahman')

        # Check in DB
        order = Order.objects.get(id=data['id'])
        self.assertEqual(order.dining_type, Order.DiningType.TAKEAWAY)
        self.assertTrue(bool(order.pickup_code))

    def test_public_customer_arrival_signal(self):
        """Customer on tracking view can announce counter arrival using order number."""
        order = Order.objects.create(
            customer_name='Tanvir Rahman',
            customer_phone='+353871234567',
            dining_type=Order.DiningType.TAKEAWAY,
            payment_method=Order.PaymentMethod.CASH,
            total_amount=Decimal('30.00'),
            status=Order.Status.READY,
        )
        self.assertIsNone(order.customer_arrived_at)

        # Call public track arrival endpoint without auth
        res = self.client.post(f'/api/v1/orders/track/{order.order_number}/arrived/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['orderNumber'], order.order_number)
        self.assertTrue(data['pickupCode'].startswith('TK-'))
        self.assertIsNotNone(data['customerArrivedAt'])

        order.refresh_from_db()
        self.assertIsNotNone(order.customer_arrived_at)

    def test_assign_pickup_rack_by_staff(self):
        """Kitchen or staff can specify the warming shelf for the bagged order."""
        order = Order.objects.create(
            customer_name='Tanvir Rahman',
            dining_type=Order.DiningType.TAKEAWAY,
            total_amount=Decimal('30.00'),
            status=Order.Status.READY,
        )
        self.client.force_authenticate(user=self.admin)
        res = self.client.patch(f'/api/v1/orders/{order.id}/pickup-rack/', {
            'pickupRack': 'Warm Shelf B',
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['pickupRack'], 'Warm Shelf B')

        order.refresh_from_db()
        self.assertEqual(order.pickup_rack, 'Warm Shelf B')

    def test_complete_takeaway_handover(self):
        """Staff marks takeaway complete, recording timestamp and auto-settling cash."""
        order = Order.objects.create(
            customer_name='Tanvir Rahman',
            dining_type=Order.DiningType.TAKEAWAY,
            payment_method=Order.PaymentMethod.CASH,
            payment_status=Order.PaymentStatus.PENDING,
            total_amount=Decimal('30.00'),
            status=Order.Status.READY,
        )
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(f'/api/v1/orders/{order.id}/complete-takeaway/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['status'], 'delivered')
        self.assertEqual(data['paymentStatus'], 'paid')
        self.assertIsNotNone(data['pickedUpAt'])

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAID)
        self.assertIsNotNone(order.picked_up_at)
