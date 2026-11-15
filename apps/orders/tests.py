from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.menu.models import Category, Dish, DishExtraOption, DishPortionOption
from apps.orders.models import Cart, CustomerAddress, Order

User = get_user_model()


class OnlineOrderingSystemTests(APITestCase):
    def setUp(self):
        # 1. Users
        self.customer = User.objects.create_user(
            username='online_customer',
            email='customer@example.com',
            phone='+353871234567',
            password='Password@123',
            role=User.Role.CUSTOMER
        )
        self.staff_member = User.objects.create_user(
            username='cashier_staff',
            email='cashier@example.com',
            phone='+353875551004',
            password='Password@123',
            role=User.Role.CASHIER_FRONT
        )

        # 2. Menu data
        self.category = Category.objects.create(name='Biryani & Rice', slug='biryani-rice')
        self.dish = Dish.objects.create(
            category=self.category,
            name='Hydrabadi Chicken Biryani',
            slug='hydrabadi-chicken-biryani',
            price=Decimal('14.50'),
            station=Dish.Station.BIRYANI,
            available_ingredients=['Onions', 'Cilantro', 'Cashews', 'Boiled Egg'],
            available_modifiers={'spice_level': ['Mild', 'Medium', 'Hot', 'Extra Hot']},
            is_available=True
        )

        # Portions & Extras
        self.portion_large = DishPortionOption.objects.create(
            dish=self.dish,
            name='Large (Family Size)',
            price_delta=Decimal('4.00')
        )
        self.extra_raita = DishExtraOption.objects.create(
            dish=self.dish,
            name='Cucumber Raita',
            price=Decimal('2.50')
        )
        self.extra_egg = DishExtraOption.objects.create(
            dish=self.dish,
            name='Extra Boiled Egg',
            price=Decimal('1.50')
        )

        # 3. Customer Address
        self.saved_address = CustomerAddress.objects.create(
            user=self.customer,
            label='Apartment',
            recipient_name='Online Customer',
            phone='+353871234567',
            address_line1='Flat 4B, 15 O\'Connell Street',
            city='Dublin',
            eircode='D01 ABC2',
            delivery_instructions='Ring buzzer 4B, 2nd floor',
            is_default=True
        )

    def test_delivery_order_asap_authenticated(self):
        self.client.force_authenticate(user=self.customer)
        url = '/api/v1/orders/'
        payload = {
            'customer_name': 'Online Customer',
            'customer_phone': '+353871234567',
            'customer_email': 'customer@example.com',
            'dining_type': 'delivery',
            'schedule_type': 'asap',
            'saved_address_id': self.saved_address.id,
            'payment_method': 'card',
            'notes': 'Please deliver to front door.',
            'items': [
                {
                    'dish_id': self.dish.id,
                    'quantity': 2,
                    'portion_option_id': self.portion_large.id,
                    'extra_option_ids': [self.extra_raita.id],
                    'customizations': {
                        'removed_ingredients': ['Cashews'],
                        'modifiers': {'spice_level': 'Hot'}
                    },
                    'special_instructions': 'Extra crispy fried onions please.'
                }
            ]
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertTrue(response.data['orderNumber'].startswith('ORD-'))
        self.assertEqual(response.data['diningType'], 'delivery')
        self.assertEqual(response.data['scheduleType'], 'asap')
        self.assertEqual(response.data['customer'], self.customer.id)
        # Unit price: 14.50 + 4.00 (portion) + 2.50 (extra) = 21.00
        # Subtotal: 21.00 * 2 = 42.00
        # Delivery fee: 3.50
        # Total: 45.50
        self.assertEqual(Decimal(str(response.data['subtotal'])), Decimal('42.00'))
        self.assertEqual(Decimal(str(response.data['deliveryFee'])), Decimal('3.50'))
        self.assertEqual(Decimal(str(response.data['totalAmount'])), Decimal('45.50'))

    def test_collection_takeaway_order(self):
        self.client.force_authenticate(user=self.customer)
        url = '/api/v1/orders/'
        payload = {
            'customer_name': 'Online Customer',
            'customer_phone': '+353871234567',
            'dining_type': 'collection',
            'schedule_type': 'asap',
            'payment_method': 'cash',
            'items': [
                {
                    'dish_id': self.dish.id,
                    'quantity': 1,
                }
            ]
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Collection has no delivery fee
        self.assertEqual(Decimal(str(response.data['deliveryFee'])), Decimal('0.00'))
        self.assertEqual(Decimal(str(response.data['totalAmount'])), Decimal('14.50'))

    def test_scheduled_order_future_time_validation(self):
        self.client.force_authenticate(user=self.customer)
        url = '/api/v1/orders/'
        future_time = timezone.now() + timedelta(hours=3)

        payload = {
            'customer_name': 'Online Customer',
            'customer_phone': '+353871234567',
            'dining_type': 'collection',
            'schedule_type': 'scheduled',
            'scheduled_for': future_time.isoformat(),
            'items': [{'dish_id': self.dish.id, 'quantity': 1}]
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['scheduleType'], 'scheduled')

        # Test past time failure
        past_time = timezone.now() - timedelta(hours=1)
        payload['scheduled_for'] = past_time.isoformat()
        res_fail = self.client.post(url, payload, format='json')
        self.assertEqual(res_fail.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('scheduled_for', res_fail.data)

    def test_guest_checkout(self):
        # Unauthenticated guest
        url = '/api/v1/orders/'
        payload = {
            'customer_name': 'Guest John',
            'customer_phone': '+353879998877',
            'customer_email': 'john.guest@example.com',
            'dining_type': 'delivery',
            'delivery_address': '77 Camden Street, Dublin 2',
            'payment_method': 'card',
            'items': [{'dish_id': self.dish.id, 'quantity': 1}]
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data['customer'])
        self.assertTrue(response.data['isGuestOrder'])
        self.assertEqual(response.data['customerEmail'], 'john.guest@example.com')

        # Guest order lookup by order_number and phone
        order_num = response.data['orderNumber']
        lookup_url = f"/api/v1/orders/lookup/?order_number={order_num}&phone=+353879998877"
        res_lookup = self.client.get(lookup_url)
        self.assertEqual(res_lookup.status_code, status.HTTP_200_OK)
        self.assertEqual(res_lookup.data['orderNumber'], order_num)

    def test_saved_addresses_crud(self):
        self.client.force_authenticate(user=self.customer)
        url = '/api/v1/orders/addresses/'

        # List saved addresses
        res_list = self.client.get(url)
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_list.data), 1)

        # Create work address
        payload = {
            'label': 'Office',
            'recipient_name': 'Customer Work',
            'phone': '+353871234567',
            'addressLine1': '2 Grand Canal Square',
            'city': 'Dublin',
            'eircode': 'D02 X525',
            'isDefault': True
        }
        res_create = self.client.post(url, payload, format='json')
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res_create.data['isDefault'])

        # Previous default address should now be is_default=False
        self.saved_address.refresh_from_db()
        self.assertFalse(self.saved_address.is_default)

    def test_saved_order_and_1_click_reorder(self):
        self.client.force_authenticate(user=self.customer)

        # Place initial order
        url = '/api/v1/orders/'
        payload = {
            'customer_name': 'Online Customer',
            'customer_phone': '+353871234567',
            'dining_type': 'collection',
            'items': [{'dish_id': self.dish.id, 'quantity': 1}]
        }
        res_order = self.client.post(url, payload, format='json')
        order_id = res_order.data['id']

        # Save as favorite order
        save_url = f"/api/v1/orders/{order_id}/toggle_save/"
        res_save = self.client.post(save_url, {'name': 'Friday Biryani Feast'}, format='json')
        self.assertEqual(res_save.status_code, status.HTTP_200_OK)
        self.assertTrue(res_save.data['isSavedOrder'])

        # Check saved orders list
        res_saved_list = self.client.get('/api/v1/orders/saved_orders/')
        self.assertEqual(res_saved_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_saved_list.data), 1)

        # 1-Click reorder
        reorder_url = f"/api/v1/orders/{order_id}/reorder/"
        res_reorder = self.client.post(reorder_url, {'dining_type': 'collection'})
        self.assertEqual(res_reorder.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(res_reorder.data['order']['id'], order_id)
        self.assertEqual(len(res_reorder.data['order']['items']), 1)

    def test_cart_workflow_add_update_remove_checkout(self):
        # 1. Add item to cart
        cart_url = '/api/v1/orders/cart/'
        add_payload = {
            'dish_id': self.dish.id,
            'quantity': 2,
            'portion_option_id': self.portion_large.id,
            'extra_option_ids': [self.extra_raita.id],
            'customizations': {'removed_ingredients': ['Onions']},
            'special_instructions': 'Extra spicy please.'
        }
        res_add = self.client.post(f"{cart_url}items/", add_payload, format='json')
        self.assertEqual(res_add.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_add.data['itemsCount'], 2)
        item_id = res_add.data['items'][0]['id']

        # 2. Update item quantity
        update_url = f"{cart_url}items/{item_id}/"
        res_update = self.client.patch(update_url, {'quantity': 3}, format='json')
        self.assertEqual(res_update.status_code, status.HTTP_200_OK)
        self.assertEqual(res_update.data['itemsCount'], 3)

        # 3. Direct checkout from cart (Guest)
        checkout_payload = {
            'customer_name': 'Cart Guest User',
            'customer_phone': '+353871112233',
            'dining_type': 'collection',
        }
        res_checkout = self.client.post(f"{cart_url}checkout/", checkout_payload, format='json')
        self.assertEqual(res_checkout.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_checkout.data['order']['customerName'], 'Cart Guest User')

        # Cart should now be empty
        res_cart_empty = self.client.get(cart_url)
        self.assertEqual(res_cart_empty.data['itemsCount'], 0)

    def test_checkout_preview(self):
        preview_url = '/api/v1/orders/preview/'
        payload = {
            'dining_type': 'delivery',
            'schedule_type': 'asap',
            'items': [
                {
                    'dish_id': self.dish.id,
                    'quantity': 2,
                    'price': Decimal('14.50')
                }
            ]
        }
        res = self.client.post(preview_url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['subtotal'], 29.0)
        self.assertEqual(res.data['deliveryFee'], 3.5)
        self.assertEqual(res.data['totalAmount'], 32.5)
        self.assertEqual(res.data['estimatedTimeMinutes'], 35)
