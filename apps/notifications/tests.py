from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.orders.models import Order, OrderItem
from apps.menu.models import Category, Dish
from .models import Notification
from .broadcaster import broadcast_order_created, broadcast_kitchen_ticket, broadcast_order_status_updated

User = get_user_model()


class NotificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='Password123!',
            role='admin',
            is_staff=True,
            is_superuser=True,
        )
        self.category = Category.objects.create(name='Biryani', slug='biryani', is_active=True)
        self.dish = Dish.objects.create(
            category=self.category,
            name='Chicken Dum Biryani',
            slug='chicken-dum-biryani',
            price='15.00',
            station='biryani',
            is_available=True,
        )
        self.order = Order.objects.create(
            order_number='ORD-TEST-001',
            customer_name='Hasan Test',
            dining_type='delivery',
            total_amount='15.00',
            status='pending',
        )
        OrderItem.objects.create(
            order=self.order,
            dish=self.dish,
            name=self.dish.name,
            quantity=1,
            price=self.dish.price,
            station='biryani',
        )

    def test_broadcast_order_created(self):
        broadcast_order_created(self.order)
        notif = Notification.objects.filter(order=self.order, type='order_created').first()
        self.assertIsNotNone(notif)
        self.assertIn('ORD-TEST-001', notif.title)
        self.assertIn('Hasan Test', notif.message)
        self.assertFalse(notif.is_read)

    def test_broadcast_kitchen_ticket(self):
        broadcast_kitchen_ticket(self.order, action='received')
        notif = Notification.objects.filter(order=self.order, type='kitchen_alert').first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.target_role, 'kitchen')

    def test_broadcast_order_status_updated(self):
        self.order.status = 'ready'
        self.order.save()
        broadcast_order_status_updated(self.order, actor_name='Chef Rajesh')
        notif = Notification.objects.filter(order=self.order, type='kitchen_ready').first()
        self.assertIsNotNone(notif)
        self.assertIn('READY', notif.title)

    def test_notifications_api_list_and_mark_read(self):
        # Create unread notifications
        Notification.objects.create(
            type='order_created',
            target_role='admin',
            title='Test Alert 1',
            message='Alert 1 message',
            is_read=False,
        )
        Notification.objects.create(
            type='order_created',
            target_role='admin',
            title='Test Alert 2',
            message='Alert 2 message',
            is_read=False,
        )

        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/v1/notifications/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['results']), 2)

        # Mark all read
        mark_res = self.client.post('/api/v1/notifications/mark-all-read/')
        self.assertEqual(mark_res.status_code, 200)
        self.assertEqual(mark_res.data['markedCount'], 2)

        # Verify list with unread=true
        unread_res = self.client.get('/api/v1/notifications/?unread=true')
        self.assertEqual(unread_res.status_code, 200)
        self.assertEqual(len(unread_res.data['results']), 0)
