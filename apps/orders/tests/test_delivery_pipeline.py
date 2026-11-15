import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.menu.models import Category, Dish, DishPortionOption, DishExtraOption
from apps.orders.models import Order

User = get_user_model()


class DeliveryPipelineTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = User.objects.create_user(username='buyer', email='buyer@example.com', role='customer')
        cls.other = User.objects.create_user(username='other', email='other@example.com', role='customer')
        cls.manager = User.objects.create_user(username='manager-pipeline', email='manager-pipeline@example.com', role='manager')
        cls.chef = User.objects.create_user(username='chef-pipeline', email='chef-pipeline@example.com', role='chef')
        cls.driver = User.objects.create_user(username='driver-pipeline', email='driver-pipeline@example.com', role='delivery_staff')
        cls.other_driver = User.objects.create_user(username='driver-other', email='driver-other@example.com', role='delivery_staff')
        cls.category = Category.objects.create(name='Delivery menu')
        cls.dish = Dish.objects.create(name='Catalog biryani', price='12.50', category=cls.category, station='biryani')
        DishPortionOption.objects.create(dish=cls.dish, name='Large', price_delta='3.00')
        DishExtraOption.objects.create(dish=cls.dish, name='Raita', price='1.50')

    def setUp(self):
        patcher = patch('apps.orders.views.process_new_order_notification')
        patcher.start()
        self.addCleanup(patcher.stop)

    def payload(self, **overrides):
        return {'customerName': 'Delivery buyer', 'customerPhone': '01000000000',
                'deliveryAddress': 'Test delivery address', 'diningType': 'delivery', 'paymentMethod': 'cash',
                'items': [{'dishId': self.dish.id, 'quantity': 1}], **overrides}

    def create_order(self, **overrides):
        response = self.client.post('/api/v1/orders/', self.payload(**overrides), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def update(self, order_id, status):
        return self.client.patch(f'/api/v1/orders/{order_id}/update_status/', {'status': status}, format='json')

    def test_prices_names_stations_and_customizations_come_from_catalog(self):
        payload = self.payload(items=[{'dishId': self.dish.id, 'quantity': 2, 'price': '0.01', 'name': 'Forged', 'station': 'dessert',
                                      'customizations': {'portionName': 'Large', 'portionPriceDelta': -500, 'extras': [{'name': 'Raita', 'price': -100}]}}])
        quote = self.client.post('/api/v1/orders/quote/', payload, format='json')
        self.assertEqual(quote.status_code, 200)
        self.assertEqual(quote.data['totalAmount'], '34.00')
        self.assertEqual(quote.data['deliveryFee'], '0.00')
        response = self.client.post('/api/v1/orders/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['items'][0]['name'], self.dish.name)
        self.assertEqual(response.data['items'][0]['station'], 'biryani')
        self.assertEqual(response.data['items'][0]['price'], '17.00')
        self.assertEqual(response.data['paymentStatus'], 'pending')
        self.assertEqual(Decimal(response.data['totalAmount']), Decimal('34'))

    def test_invalid_checkout_is_atomic_and_online_payment_is_not_simulated(self):
        for overrides in [{'items': []}, {'items': [{'dishId': 999999, 'quantity': 1}]},
                          {'items': [{'dishId': self.dish.id, 'quantity': 0}]},
                          {'items': [{'dishId': self.dish.id, 'quantity': 1, 'customizations': {'extras': [{'name': 'invented'}]}}]},
                          {'deliveryAddress': ''}, {'customerPhone': ''}, {'paymentMethod': 'card'},
                          {'totalAmount': '0.01'}, {'scheduledFor': (timezone.now() - timedelta(hours=1)).isoformat()}]:
            response = self.client.post('/api/v1/orders/', self.payload(**overrides), format='json')
            self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(Order.objects.count(), 0)
        self.dish.is_available = False
        self.dish.save()
        self.assertEqual(self.client.post('/api/v1/orders/', self.payload(), format='json').status_code, 400)

    def test_retry_returns_saved_order_once_and_rejects_reused_key(self):
        payload = self.payload(clientRequestId=str(uuid.uuid4()))
        first = self.client.post('/api/v1/orders/', payload, format='json')
        second = self.client.post('/api/v1/orders/', payload, format='json')
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertEqual(first.data['customerContactToken'], second.data['customerContactToken'])
        self.assertEqual(first.data['customerContactToken'], str(Order.objects.get(pk=first.data['id']).customer_chat_token))
        public = self.client.get(f"/api/v1/orders/track/{first.data['orderNumber']}/")
        self.assertNotIn('customerContactToken', public.data)
        self.assertEqual(Order.objects.count(), 1)
        self.dish.refresh_from_db()
        self.assertEqual(self.dish.orders_count, 1)
        conflict = self.client.post('/api/v1/orders/', {**payload, 'customerName': 'Different'}, format='json')
        self.assertEqual(conflict.status_code, 409)

    def test_linked_checkout_uses_owner_jwt_instead_of_exposing_guest_credentials(self):
        self.client.force_authenticate(self.customer)
        order = self.create_order()
        self.assertNotIn('customerContactToken', order)
        self.assertEqual(order['customer'], self.customer.id)

    def test_entire_delivery_pipeline_persists_and_enforces_roles(self):
        self.client.force_authenticate(self.customer)
        created = self.create_order()
        pk = created['id']
        self.assertEqual(self.update(pk, 'delivered').status_code, 403)
        self.assertEqual(self.client.patch(f'/api/v1/orders/{pk}/', {'status': 'delivered'}).status_code, 405)
        self.assertEqual(self.client.delete(f'/api/v1/orders/{pk}/').status_code, 405)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f'/api/v1/orders/{pk}/').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/orders/').data['count'], 0)
        self.client.force_authenticate(self.chef)
        queue = self.client.get('/api/v1/orders/kitchen/?station=biryani')
        self.assertIn(pk, [order['id'] for order in queue.data])
        self.assertEqual(self.update(pk, 'ready').status_code, 400)
        self.assertEqual(self.update(pk, 'preparing').status_code, 200)
        self.assertEqual(self.update(pk, 'ready').status_code, 200)
        self.assertEqual(self.update(pk, 'delivered').status_code, 403)
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.update(pk, 'out_for_delivery').status_code, 400)
        assign = self.client.post(f'/api/v1/orders/{pk}/assign_delivery/', {'delivery_staff_id': self.driver.id}, format='json')
        self.assertEqual(assign.status_code, 200, assign.data)
        self.client.force_authenticate(self.other_driver)
        self.assertEqual(self.update(pk, 'out_for_delivery').status_code, 404)
        self.assertEqual(len(self.client.get('/api/v1/orders/deliveries/').data), 0)
        self.client.force_authenticate(self.driver)
        self.assertEqual(self.client.patch('/api/v1/rider/me/', {'on_duty': True}, format='json').status_code, 200)
        self.assertEqual(self.client.post(f'/api/v1/rider/jobs/{pk}/accept/').status_code, 200)
        self.client.force_authenticate(self.manager)
        ticket = self.client.post(f'/api/v1/orders/{pk}/handover/', {'rider_id': self.driver.id, 'bag_count': 1, 'sealed': True,
            'items': [{'item_id': item.id, 'quantity': item.quantity} for item in Order.objects.get(pk=pk).items.all()]}, format='json')
        self.assertEqual(ticket.status_code, 200, ticket.data)
        self.client.force_authenticate(self.driver)
        self.assertEqual(self.client.post(f'/api/v1/rider/jobs/{pk}/pickup/', {'ticket_code': ticket.data['ticketCode'], 'bag_count': 1}, format='json').status_code, 200)
        self.assertEqual(self.client.post(f'/api/v1/orders/{pk}/collect-cash/', {'payment_status': 'paid'}, format='json').status_code, 400)
        self.assertEqual(self.client.post(f'/api/v1/rider/jobs/{pk}/arrive/').status_code, 200)
        self.assertEqual(self.client.post(f'/api/v1/rider/jobs/{pk}/complete/', {'ticket_code': ticket.data['ticketCode'], 'bag_count': 1, 'recipient_confirmed': True}, format='json').status_code, 200)
        payment = self.client.post(f'/api/v1/orders/{pk}/collect-cash/', {'payment_status': 'paid'}, format='json')
        self.assertEqual(payment.status_code, 200)
        self.assertEqual(payment.data['paymentStatus'], 'paid')
        self.assertEqual(self.update(pk, 'preparing').status_code, 403)
        self.client.force_authenticate(None)
        # A fresh public request reads database state; no UI/local state can supply this.
        tracked = self.client.get(f"/api/v1/orders/track/{created['orderNumber']}/")
        self.assertEqual(tracked.status_code, 200)
        self.assertEqual(tracked.data['status'], 'delivered')
        self.assertEqual(tracked.data['paymentStatus'], 'paid')
        self.assertEqual([event['status'] for event in tracked.data['events']], ['pending', 'preparing', 'ready', 'out_for_delivery', 'delivered'])
        self.assertEqual(self.client.get(f'/api/v1/orders/track/{pk}/').status_code, 404)
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get('/api/v1/orders/').data['results'][0]['id'], pk)

    def test_takeaway_schedule_and_terminal_states(self):
        created = self.create_order(diningType='takeaway', scheduledFor=(timezone.now() + timedelta(hours=2)).isoformat())
        self.client.force_authenticate(self.manager)
        self.assertNotIn(created['id'], [order['id'] for order in self.client.get('/api/v1/orders/kitchen/').data])
        self.assertEqual(self.update(created['id'], 'preparing').status_code, 400)
        self.assertEqual(self.update(created['id'], 'cancelled').status_code, 200)
        self.assertEqual(self.update(created['id'], 'preparing').status_code, 400)
        self.client.force_authenticate(None)
        takeaway = self.create_order(diningType='takeaway')
        self.assertEqual(takeaway['deliveryFee'], '0.00')
        self.client.force_authenticate(self.manager)
        for next_status in ['preparing', 'ready', 'delivered']:
            self.assertEqual(self.update(takeaway['id'], next_status).status_code, 200)

    def test_hidden_categories_and_inactive_drivers_are_rejected(self):
        self.category.is_active = False
        self.category.save()
        self.assertEqual(self.client.post('/api/v1/orders/quote/', self.payload(), format='json').status_code, 400)
        self.category.is_active = True
        self.category.save()
        order = self.create_order()
        self.driver.is_active = False
        self.driver.save()
        self.client.force_authenticate(self.manager)
        response = self.client.post(f"/api/v1/orders/{order['id']}/assign_delivery/", {'delivery_staff_id': self.driver.id}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(self.driver.id, [driver['id'] for driver in self.client.get('/api/v1/orders/delivery-staff/').data])

    def test_openapi_includes_actions_request_fields_and_security(self):
        from drf_spectacular.generators import SchemaGenerator
        schema = SchemaGenerator().get_schema(public=True)
        paths = schema['paths']
        self.assertIn('/api/v1/orders/quote/', paths)
        self.assertIn('/api/v1/orders/{id}/collect-cash/', paths)
        self.assertIn('requestBody', paths['/api/v1/orders/{id}/assign_delivery/']['post'])
        self.assertTrue(paths['/api/v1/orders/{id}/update_status/']['patch']['security'])
        self.assertIn({}, paths['/api/v1/orders/quote/']['post']['security'])
