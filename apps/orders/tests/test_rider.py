from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.orders.models import DeliveryEvent, DeliveryJob, Order, OrderItem
from apps.orders.delivery_workflow import DeliveryWorkflow

User = get_user_model()


class RiderWorkspaceTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rider = User.objects.create_user(username='rider', email='rider@example.com', role='delivery_staff', first_name='Rider', phone='01000000000')
        cls.other = User.objects.create_user(username='other-rider', email='other-rider@example.com', role='delivery_staff')
        cls.customer = User.objects.create_user(username='rider-buyer', email='rider-buyer@example.com', role='customer')
        cls.manager = User.objects.create_user(username='rider-manager', email='rider-manager@example.com', role='manager')

    def setUp(self):
        self.order = Order.objects.create(customer=self.customer, customer_name='Saved Buyer', customer_phone='01011111111',
            delivery_address='Saved delivery address', delivery_postal_code='R93 TEST', dining_type='delivery', total_amount='19.50', status='ready', notes='Ring the buzzer')
        OrderItem.objects.create(order=self.order, name='Saved menu item', quantity=2, price='9.75')
        with transaction.atomic():
            DeliveryWorkflow.assign(self.order, self.rider, self.manager)
        self.client.force_authenticate(self.rider)

    def action(self, action, data=None):
        if data is None and action in ['pickup', 'complete']:
            job = DeliveryJob.objects.get(order=self.order)
            data = {'ticket_code': job.handover_code or self.order.order_number, 'bag_count': job.bag_count or 1}
            if action == 'complete':
                data['recipient_confirmed'] = True
        return self.client.post(f'/api/v1/rider/jobs/{self.order.id}/{action}/', data or {}, format='json')

    def release_kitchen(self):
        client = APIClient()
        client.force_authenticate(self.manager)
        response = client.post(f'/api/v1/orders/{self.order.id}/handover/', {
            'rider_id': self.rider.id, 'bag_count': 1, 'sealed': True,
            'items': [{'item_id': item.id, 'quantity': item.quantity} for item in self.order.items.all()],
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return response

    def start_shift(self):
        response = self.client.patch('/api/v1/rider/me/', {'on_duty': True, 'vehicle_type': 'motorbike', 'vehicle_registration': 'TEST-PLATE'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return response

    def test_full_workflow_cash_and_fresh_reload(self):
        me = self.client.get('/api/v1/rider/me/')
        self.assertFalse(me.data['onDuty'])
        self.assertEqual(me.data['pendingAssignments'], 1)
        self.assertEqual(self.action('accept').status_code, 400)
        self.start_shift()
        for action, stage in [('accept', 'accepted'), ('pickup', 'picked_up'), ('arrive', 'arrived'), ('complete', 'delivered')]:
            if action == 'pickup':
                self.release_kitchen()
            response = self.action(action)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['delivery']['stage'], stage)
            replay = self.action(action)
            self.assertEqual(replay.status_code, 200, replay.data)
        self.assertEqual(self.client.get('/api/v1/rider/jobs/').data['count'], 1)
        blocked = self.client.patch('/api/v1/rider/me/', {'on_duty': False}, format='json')
        self.assertEqual(blocked.status_code, 400)
        receipt = self.action('collect-cash')
        self.assertEqual(receipt.data['paymentStatus'], 'paid')
        self.assertEqual(self.action('collect-cash').status_code, 200)
        self.assertEqual(DeliveryEvent.objects.filter(order=self.order, action='cash_collected').count(), 1)
        self.assertEqual(DeliveryEvent.objects.get(order=self.order, action='cash_collected').amount, Decimal('19.50'))
        fresh = APIClient()
        fresh.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.rider).access_token}')
        saved = fresh.get(f'/api/v1/rider/jobs/{self.order.id}/').data
        self.assertEqual(saved['delivery']['stage'], 'delivered')
        self.assertTrue(saved['delivery']['arrivedAt'])
        self.assertTrue(saved['delivery']['cashCollectedAt'])
        self.assertEqual(saved['availableActions'], [])
        summary = fresh.get('/api/v1/rider/me/').data
        self.assertEqual(summary['cashCollectedToday'], '19.50')
        self.assertEqual(summary['cashOutstanding'], '0.00')
        self.assertEqual(summary['deliveredToday'], 1)
        self.assertEqual(summary['vehicleType'], 'motorbike')
        self.assertEqual(fresh.get('/api/v1/rider/jobs/?scope=active').data['count'], 0)
        self.assertEqual(fresh.get('/api/v1/rider/jobs/?scope=completed').data['count'], 1)
        self.assertEqual(fresh.patch('/api/v1/rider/me/', {'on_duty': False}, format='json').status_code, 200)

    def test_cannot_skip_kitchen_pickup_arrival_or_cash_rules(self):
        self.start_shift()
        self.assertEqual(self.action('pickup').status_code, 400)
        self.assertEqual(self.action('complete').status_code, 400)
        self.assertEqual(self.action('collect-cash').status_code, 400)
        self.assertEqual(self.action('accept').status_code, 200)
        self.order.status = 'preparing'
        self.order.save()
        self.assertEqual(self.action('pickup').status_code, 400)
        self.order.status = 'ready'
        self.order.save()
        self.release_kitchen()
        self.assertEqual(self.action('pickup').status_code, 200)
        self.assertEqual(self.action('complete').status_code, 400)
        legacy = self.client.patch(f'/api/v1/orders/{self.order.id}/update_status/', {'status': 'delivered'}, format='json')
        self.assertEqual(legacy.status_code, 400)
        self.assertEqual(self.client.patch('/api/v1/rider/me/', {'on_duty': False}, format='json').status_code, 400)
        self.assertEqual(self.action('decline', {'note': 'Too late'}).status_code, 400)

    def test_issue_blocks_progress_and_only_operations_can_resolve(self):
        self.start_shift()
        self.action('accept')
        issue = self.action('report-issue', {'code': 'order_problem', 'note': 'Packaging damaged'})
        self.assertEqual(issue.status_code, 200, issue.data)
        self.assertTrue(issue.data['delivery']['hasIssue'])
        self.assertNotIn('pickup', issue.data['availableActions'])
        self.assertEqual(self.action('pickup').status_code, 400)
        resolution_url = f'/api/v1/orders/{self.order.id}/delivery/resolve-issue/'
        self.assertEqual(self.client.post(resolution_url, {'note': 'Forged resolution'}, format='json').status_code, 403)
        self.client.force_authenticate(None)
        public = self.client.get(f'/api/v1/orders/track/{self.order.order_number}/').data
        self.assertTrue(public['deliveryProgress']['hasIssue'])
        self.assertNotIn('Packaging damaged', str(public))
        self.client.force_authenticate(self.manager)
        activity = self.client.get(f'/api/v1/orders/{self.order.id}/delivery/').data
        self.assertEqual(activity['issue']['note'], 'Packaging damaged')
        self.assertEqual(self.client.patch(f'/api/v1/orders/{self.order.id}/update_status/', {'status': 'out_for_delivery'}, format='json').status_code, 400)
        resolved = self.client.post(resolution_url, {'note': 'Repacked and checked'}, format='json')
        self.assertEqual(resolved.status_code, 200, resolved.data)
        self.assertFalse(resolved.data['hasIssue'])
        self.client.force_authenticate(self.rider)
        self.release_kitchen()
        self.assertEqual(self.action('pickup').status_code, 200)

    def test_decline_keeps_order_and_allows_reassignment_with_audit(self):
        self.start_shift()
        self.action('accept')
        self.assertEqual(self.action('decline', {'note': ''}).status_code, 400)
        self.assertEqual(self.action('decline', {'note': 'Vehicle repair needed'}).status_code, 204)
        self.order.refresh_from_db()
        self.assertIsNone(self.order.assigned_delivery_staff_id)
        self.assertEqual(self.order.status, 'ready')
        self.assertEqual(self.client.get('/api/v1/rider/jobs/').data['count'], 0)
        self.client.force_authenticate(self.manager)
        assigned = self.client.post(f'/api/v1/orders/{self.order.id}/assign_delivery/', {'delivery_staff_id': self.other.id}, format='json')
        self.assertEqual(assigned.status_code, 200, assigned.data)
        self.assertEqual(assigned.data['order']['deliveryProgress']['stage'], 'assigned')
        self.assertTrue(DeliveryEvent.objects.filter(order=self.order, action='declined', actor=self.rider).exists())

    def test_role_and_assignment_isolation(self):
        for user in [None, self.customer, self.manager]:
            self.client.force_authenticate(user)
            self.assertIn(self.client.get('/api/v1/rider/me/').status_code, [401, 403])
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get('/api/v1/rider/jobs/').data['count'], 0)
        for action in ['accept', 'pickup', 'arrive', 'complete', 'collect-cash', 'decline', 'report-issue']:
            self.assertEqual(self.action(action).status_code, 404)
        self.client.force_authenticate(self.rider)
        result = self.client.get(f'/api/v1/rider/jobs/{self.order.id}/').data
        self.assertNotIn('customerEmail', result)
        self.assertEqual(result['items'][0]['name'], 'Saved menu item')
        self.assertEqual(self.client.get('/api/v1/rider/jobs/?scope=unknown').status_code, 400)

    def test_failed_delivery_requires_dispatch_approval_and_recorded_return(self):
        self.start_shift()
        self.action('accept')
        self.release_kitchen()
        self.action('pickup')
        self.assertEqual(self.action('confirm-return').status_code, 400)
        self.action('report-issue', {'code': 'customer_unavailable', 'note': 'No answer after calling'})
        url = f'/api/v1/orders/{self.order.id}/delivery/request-return/'
        self.assertEqual(self.client.post(url, {'note': 'Self-approved'}, format='json').status_code, 403)
        self.client.force_authenticate(self.manager)
        returned = self.client.post(url, {'note': 'Customer contacted. Return to restaurant.'}, format='json')
        self.assertEqual(returned.status_code, 200, returned.data)
        self.assertEqual(returned.data['stage'], 'returning')
        self.assertEqual(self.client.patch(f'/api/v1/orders/{self.order.id}/update_status/', {'status': 'delivered'}, format='json').status_code, 400)
        self.client.force_authenticate(self.rider)
        self.assertEqual(self.client.patch('/api/v1/rider/me/', {'on_duty': False}, format='json').status_code, 400)
        response = self.action('confirm-return')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['status'], 'cancelled')
        self.assertEqual(response.data['delivery']['stage'], 'returned')
        self.assertTrue(response.data['delivery']['returnedAt'])
        self.assertEqual(self.action('confirm-return').status_code, 200)
        self.assertEqual(DeliveryEvent.objects.filter(order=self.order, action='returned').count(), 1)
        self.assertEqual(self.action('collect-cash').status_code, 400)
        self.assertEqual(self.client.get('/api/v1/rider/jobs/?scope=completed').data['count'], 1)

    def test_schema_exposes_rider_actions_and_request_auth(self):
        schema = SchemaGenerator().get_schema(public=True)
        for action in ['accept', 'pickup', 'arrive', 'complete', 'collect-cash', 'decline', 'report-issue', 'confirm-return']:
            operation = schema['paths'][f'/api/v1/rider/jobs/{{id}}/{action}/']['post']
            self.assertTrue(operation['security'])
        self.assertIn('requestBody', schema['paths']['/api/v1/rider/me/']['patch'])
        self.assertIn('requestBody', schema['paths']['/api/v1/rider/jobs/{id}/report-issue/']['post'])
        self.assertIn('/api/v1/orders/{id}/delivery/resolve-issue/', schema['paths'])
        for path in ['/api/v1/orders/{order_id}/handover/', '/api/v1/orders/{order_id}/delivery/contact/',
                     '/api/v1/orders/{order_id}/delivery/contact/messages/', '/api/v1/orders/track/{order_number}/contact/',
                     '/api/v1/orders/track/{order_number}/contact/messages/', '/api/v1/rider/jobs/{id}/contact/',
                     '/api/v1/rider/jobs/{id}/contact/messages/']:
            self.assertIn(path, schema['paths'])
        components = schema['components']['schemas']
        self.assertIn('ticket_code', components['PickupVerificationRequest']['required'])
        self.assertIn('recipient_confirmed', components['DeliveryVerificationRequest']['required'])
        self.assertIn('rider_id', components['KitchenHandoverRequest']['required'])
        self.assertIn('client_message_id', components['MessageCreateRequest']['required'])
        self.assertIn('customerContactToken', components['CheckoutResponse']['properties'])
        parameters = schema['paths']['/api/v1/orders/track/{order_number}/contact/']['get']['parameters']
        self.assertTrue(any(parameter['name'] == 'X-Order-Contact-Token' and parameter['in'] == 'header' for parameter in parameters))
