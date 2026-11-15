from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.inventory.models import InventoryItem
from apps.orders.models import Order
from .models import Notification, NotificationTemplate, NotificationPreference
from .services import (
    notify_new_order,
    notify_order_accepted,
    notify_order_preparing,
    notify_order_ready,
    notify_order_dispatched,
    notify_order_completed,
    notify_order_cancelled,
    notify_payment_confirmation,
    notify_payment_failed,
    notify_low_inventory,
    notify_admin_alert,
    send_notification,
)

User = get_user_model()


class NotificationsSystemTests(APITestCase):
    """
    Test suite for Restaurant Notifications System:
    Order lifecycles, payments, low inventory, admin alerts, multi-channel dispatch,
    in-app inbox, read state management, and user preferences.
    """

    def setUp(self):
        # Admin User
        self.admin = User.objects.create_user(
            username='admin_notif',
            email='admin@amberspice.com',
            phone='+353871112222',
            password='Password123!',
            role=User.Role.OWNER_ADMIN
        )

        # Customer User
        self.customer = User.objects.create_user(
            username='customer_john',
            email='john@example.com',
            phone='+353875556677',
            password='Password123!',
            role=User.Role.CUSTOMER,
            first_name='John',
            last_name='Doe'
        )

        # Sample Order
        self.order = Order.objects.create(
            customer=self.customer,
            customer_name='John Doe',
            customer_email='john@example.com',
            customer_phone='+353875556677',
            dining_type=Order.DiningType.DELIVERY,
            delivery_address='42 Grafton Street, Dublin',
            status=Order.Status.PENDING,
            payment_status=Order.PaymentStatus.PAID,
            total_amount=Decimal('42.50'),
            estimated_time_minutes=25
        )

        # Sample Inventory Item
        self.item = InventoryItem.objects.create(
            name='Basmati Rice',
            category='grain',
            unit='kg',
            current_stock=Decimal('4.00'),
            minimum_stock=Decimal('10.00'),
            purchase_price=Decimal('2.50')
        )

    def test_new_order_notifications(self):
        """
        Tests customer confirmation and kitchen alert upon new order placement.
        """
        notifs = notify_new_order(self.order)
        self.assertGreaterEqual(len(notifs), 2)

        # Customer notification
        cust_notifs = [n for n in notifs if n.recipient_role == 'customer']
        self.assertTrue(len(cust_notifs) > 0)
        self.assertIn(self.order.order_number, cust_notifs[0].title)

        # Staff notification
        staff_notifs = [n for n in notifs if n.recipient_role == 'kitchen']
        self.assertTrue(len(staff_notifs) > 0)

    def test_order_lifecycle_notifications(self):
        """
        Tests notifications for Order Acceptance, Preparation, Ready, Dispatched, Completed, and Cancelled.
        """
        # Accepted
        notifs_accepted = notify_order_accepted(self.order)
        self.assertEqual(notifs_accepted[0].notification_type, Notification.NotificationType.ORDER_ACCEPTED)

        # Preparing
        notifs_prep = notify_order_preparing(self.order)
        self.assertEqual(notifs_prep[0].notification_type, Notification.NotificationType.ORDER_PREPARING)

        # Ready
        notifs_ready = notify_order_ready(self.order)
        self.assertEqual(notifs_ready[0].notification_type, Notification.NotificationType.ORDER_READY)

        # Dispatched
        notifs_disp = notify_order_dispatched(self.order, driver_name="Dave Driver", eta_minutes=12)
        self.assertEqual(notifs_disp[0].notification_type, Notification.NotificationType.ORDER_DISPATCHED)
        self.assertIn("Dave Driver", notifs_disp[0].message)

        # Completed
        notifs_comp = notify_order_completed(self.order)
        self.assertEqual(notifs_comp[0].notification_type, Notification.NotificationType.ORDER_COMPLETED)

        # Cancelled
        notifs_canc = notify_order_cancelled(self.order, reason="Kitchen closing early")
        self.assertEqual(notifs_canc[0].notification_type, Notification.NotificationType.ORDER_CANCELLED)
        self.assertIn("Kitchen closing early", notifs_canc[0].message)

    def test_payment_notifications(self):
        """
        Tests Payment Confirmation and Payment Failed alerts.
        """
        # Payment Confirmed
        notifs_conf = notify_payment_confirmation(self.order, payment_method="Stripe Card")
        self.assertEqual(notifs_conf[0].notification_type, Notification.NotificationType.PAYMENT_CONFIRMATION)
        self.assertIn("Stripe Card", notifs_conf[0].message)

        # Payment Failed
        notifs_fail = notify_payment_failed(self.order, reason="Insufficient funds")
        self.assertEqual(notifs_fail[0].notification_type, Notification.NotificationType.PAYMENT_FAILED)
        self.assertIn("Insufficient funds", notifs_fail[0].message)

    def test_low_inventory_notification(self):
        """
        Tests Low Inventory threshold alert to manager and kitchen.
        """
        notifs = notify_low_inventory(self.item)
        self.assertGreaterEqual(len(notifs), 1)
        self.assertEqual(notifs[0].notification_type, Notification.NotificationType.LOW_INVENTORY)
        self.assertIn("Basmati Rice", notifs[0].title)

    def test_admin_alert_notification(self):
        """
        Tests urgent Admin System Alert broadcast.
        """
        notifs = notify_admin_alert(
            title="Cold Storage Temp Warning",
            message="Walk-in cooler #2 temperature reached 8°C. Immediate inspection required.",
            urgency="critical"
        )
        self.assertGreaterEqual(len(notifs), 1)
        self.assertEqual(notifs[0].notification_type, Notification.NotificationType.ADMIN_ALERT)
        self.assertIn("CRITICAL", notifs[0].title)

    def test_user_inbox_and_mark_read_api(self):
        """
        Tests customer in-app notification inbox, unread count, and mark-as-read endpoints.
        """
        # Create 2 unread notifications for customer
        Notification.objects.create(
            recipient=self.customer,
            notification_type=Notification.NotificationType.NEW_ORDER,
            channel=Notification.Channel.IN_APP,
            title="Notification 1",
            message="Message 1",
            is_read=False
        )
        notif2 = Notification.objects.create(
            recipient=self.customer,
            notification_type=Notification.NotificationType.ORDER_READY,
            channel=Notification.Channel.IN_APP,
            title="Notification 2",
            message="Message 2",
            is_read=False
        )

        self.client.force_authenticate(user=self.customer)

        # Check Unread Count API
        res_count = self.client.get('/api/v1/notifications/unread-count/')
        self.assertEqual(res_count.status_code, status.HTTP_200_OK)
        self.assertEqual(res_count.data['unreadCount'], 2)

        # Mark single notification as read
        res_mark = self.client.post(f'/api/v1/notifications/{notif2.id}/mark-read/')
        self.assertEqual(res_mark.status_code, status.HTTP_200_OK)
        self.assertTrue(res_mark.data['isRead'])

        # Check updated count
        res_count2 = self.client.get('/api/v1/notifications/unread-count/')
        self.assertEqual(res_count2.data['unreadCount'], 1)

        # Mark all read
        res_all = self.client.post('/api/v1/notifications/mark-all-read/')
        self.assertEqual(res_all.status_code, status.HTTP_200_OK)
        self.assertEqual(res_all.data['markedCount'], 1)

    def test_notification_channel_preferences(self):
        """
        Tests user updating channel preferences (e.g. opting out of SMS).
        """
        self.client.force_authenticate(user=self.customer)

        # Update preferences to disable SMS
        res_pref = self.client.put('/api/v1/notifications/preferences/', {
            'sms_enabled': False,
            'email_enabled': True
        })
        self.assertEqual(res_pref.status_code, status.HTTP_200_OK)
        self.assertFalse(res_pref.data['preferences']['sms_enabled'])

        # Send notification asking for [IN_APP, SMS]
        notifs = send_notification(
            event_type=Notification.NotificationType.ORDER_PREPARING,
            recipient=self.customer,
            title="Food Prep",
            message="Cooking",
            channels=[Notification.Channel.IN_APP, Notification.Channel.SMS]
        )
        # SMS should have been skipped according to user preferences!
        channels_dispatched = [n.channel for n in notifs]
        self.assertIn(Notification.Channel.IN_APP, channels_dispatched)
        self.assertNotIn(Notification.Channel.SMS, channels_dispatched)

    def test_template_rendering_with_dynamic_placeholders(self):
        """
        Tests template substitution with dynamic parameters.
        """
        template = NotificationTemplate.objects.create(
            event_type=Notification.NotificationType.ORDER_READY,
            channel=Notification.Channel.SMS,
            title_template="Ready: Order #{order_number}",
            body_template="Hi {customer_name}, order #{order_number} is ready for {dining_type}!"
        )

        title, body = template.render({
            'order_number': 'ORD-999',
            'customer_name': 'Jane',
            'dining_type': 'collection'
        })
        self.assertEqual(title, "Ready: Order #ORD-999")
        self.assertEqual(body, "Hi Jane, order #ORD-999 is ready for collection!")

