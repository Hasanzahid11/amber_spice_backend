from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.menu.models import Category, Dish
from ..models import Order, OrderItem

User = get_user_model()


class OrderAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = User.objects.create_user(
            username='order-customer',
            email='order-customer@example.com',
            role=User.Role.CUSTOMER,
        )
        cls.manager = User.objects.create_user(
            username='order-manager',
            email='order-manager@example.com',
            role=User.Role.MANAGER,
        )
        cls.category = Category.objects.create(name='Biryani & Rice', order=1)
        cls.dish = Dish.objects.create(
            category=cls.category,
            name='Chicken Dum Biryani',
            price=Decimal('16.50'),
            is_available=True,
        )

    def setUp(self):
        self.list_url = reverse('order-list')
        patcher = patch('apps.orders.views.process_new_order_notification')
        self.mock_task = patcher.start()
        self.addCleanup(patcher.stop)

    def test_guest_customer_can_create_order(self):
        payload = {
            'customerName': 'Rahim Uddin',
            'customerPhone': '+353 87 123 4567',
            'diningType': 'delivery',
            'deliveryAddress': '12 Grafton Street, Dublin 2',
            'paymentMethod': 'card',
            'subtotal': '16.50',
            'tax': '1.50',
            'deliveryFee': '2.50',
            'totalAmount': '20.50',
            'items': [
                {
                    'dishId': self.dish.id,
                    'name': 'Chicken Dum Biryani',
                    'quantity': 1,
                    'price': '16.50',
                    'station': 'biryani',
                    'customizations': {'spicyLevel': 2},
                }
            ],
        }
        response = self.client.post(self.list_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('orderNumber', response.data)
        self.assertTrue(response.data['orderNumber'].startswith('ORD-'))
        self.assertEqual(response.data['customerName'], 'Rahim Uddin')
        self.assertEqual(response.data['status'], 'pending')
        self.assertEqual(len(response.data['items']), 1)
        self.assertEqual(response.data['items'][0]['name'], 'Chicken Dum Biryani')

        # Check DB
        order = Order.objects.get(order_number=response.data['orderNumber'])
        self.assertEqual(order.customer_name, 'Rahim Uddin')
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.dining_type, 'delivery')

    def test_authenticated_customer_order_links_user(self):
        self.client.force_authenticate(user=self.customer)
        payload = {
            'customer_name': 'Order Customer',
            'dining_type': 'takeaway',
            'payment_method': 'cash',
            'total_amount': '16.50',
            'items': [
                {
                    'dish_id': self.dish.id,
                    'name': 'Chicken Dum Biryani',
                    'quantity': 1,
                    'price': '16.50',
                }
            ],
        }
        response = self.client.post(self.list_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(order_number=response.data['orderNumber'])
        self.assertEqual(order.customer, self.customer)

    def test_manager_can_view_all_orders(self):
        Order.objects.create(customer_name='Alice', total_amount=Decimal('30.00'))
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data['results'] if 'results' in response.data else response.data
        self.assertGreaterEqual(len(data), 1)

    def test_guest_can_track_order_by_order_number(self):
        order = Order.objects.create(
            order_number='ORD-TEST-12345',
            customer_name='Farhan',
            dining_type='delivery',
            payment_method='card',
            total_amount=Decimal('25.00'),
            delivery_address='Dublin 4',
        )
        OrderItem.objects.create(order=order, name='Chicken Biryani', quantity=1, price=Decimal('25.00'))

        track_url = f"/api/v1/orders/track/{order.order_number}/"
        response = self.client.get(track_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['orderNumber'], 'ORD-TEST-12345')
        self.assertEqual(response.data['customerName'], 'Farhan')
        self.assertEqual(len(response.data['items']), 1)
