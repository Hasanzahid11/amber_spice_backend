import uuid

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.orders.models import Order, OrderItem, RiderProfile, DeliveryJob, DeliveryMessage, DeliveryEvent
from apps.orders.delivery_workflow import DeliveryWorkflow

User = get_user_model()


class HandoverAndContactTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = User.objects.create_user(username='chat-buyer', email='chat-buyer@example.com', role='customer')
        cls.other = User.objects.create_user(username='chat-other', email='chat-other@example.com', role='customer')
        cls.rider = User.objects.create_user(username='chat-rider', email='chat-rider@example.com', role='delivery_staff', first_name='Assigned Rider', phone='01000000000')
        cls.other_rider = User.objects.create_user(username='chat-other-rider', email='chat-other-rider@example.com', role='delivery_staff')
        cls.chef = User.objects.create_user(username='chat-chef', email='chat-chef@example.com', role='chef')
        cls.manager = User.objects.create_user(username='chat-manager', email='chat-manager@example.com', role='manager')

    def setUp(self):
        self.order = Order.objects.create(customer=self.customer, customer_name='Ticket Buyer', customer_phone='01011111111',
            delivery_address='Saved delivery address', dining_type='delivery', status='ready', total_amount='18.00')
        self.item = OrderItem.objects.create(order=self.order, name='Checked biryani', quantity=2, price='9.00', customizations={'spiceLevel': 'Mild'})
        RiderProfile.objects.create(user=self.rider, on_duty=True, vehicle_type='motorbike', vehicle_registration='TEST RIDER')
        with transaction.atomic():
            DeliveryWorkflow.assign(self.order, self.rider, self.manager)
        self.rider_client = APIClient()
        self.rider_client.force_authenticate(self.rider)
        self.rider_client.post(f'/api/v1/rider/jobs/{self.order.id}/accept/')
        self.client.force_authenticate(self.chef)
        self.ticket_url = f'/api/v1/orders/{self.order.id}/handover/'
        self.contact_url = f'/api/v1/orders/track/{self.order.order_number}/contact/'
        self.messages_url = self.contact_url + 'messages/'
        self.rider_url = f'/api/v1/rider/jobs/{self.order.id}/'

    def handover(self, **overrides):
        payload = {'rider_id': self.rider.id, 'bag_count': 2, 'sealed': True, 'items': [{'item_id': self.item.id, 'quantity': 2}], **overrides}
        return self.client.post(self.ticket_url, payload, format='json')

    def pickup(self):
        ticket = self.handover()
        self.assertEqual(ticket.status_code, 200, ticket.data)
        self.code = ticket.data['ticketCode']
        picked = self.rider_client.post(self.rider_url + 'pickup/', {'ticket_code': self.code, 'bag_count': 2}, format='json')
        self.assertEqual(picked.status_code, 200, picked.data)
        return picked

    def test_ticket_matches_exact_food_customer_rider_and_bags(self):
        self.assertEqual(self.rider_client.post(self.rider_url + 'pickup/', {'ticket_code': 'NO-TICKET', 'bag_count': 2}, format='json').status_code, 400)
        for overrides in [{'rider_id': self.other_rider.id}, {'sealed': False}, {'items': []},
                          {'items': [{'item_id': self.item.id, 'quantity': 1}]},
                          {'items': [{'item_id': self.item.id, 'quantity': 2}, {'item_id': self.item.id, 'quantity': 2}]}]:
            self.assertEqual(self.handover(**overrides).status_code, 400)
        ticket = self.handover()
        self.assertEqual(ticket.data['customerName'], 'Ticket Buyer')
        self.assertEqual(ticket.data['assignedRider']['id'], self.rider.id)
        self.assertEqual(ticket.data['items'][0]['quantity'], 2)
        code = ticket.data['ticketCode']
        self.assertEqual(len(code), 8)
        reloaded = self.client.get(self.ticket_url)
        self.assertEqual(reloaded.data['ticketCode'], code)
        self.assertEqual(self.handover().data['handoverAt'], ticket.data['handoverAt'])
        wrong_bag = self.rider_client.post(self.rider_url + 'pickup/', {'ticket_code': code, 'bag_count': 1}, format='json')
        self.assertEqual(wrong_bag.status_code, 400)
        self.assertEqual(self.rider_client.post(self.rider_url + 'pickup/', {'ticket_code': 'WRONG000', 'bag_count': 2}, format='json').status_code, 400)
        correct = self.rider_client.post(self.rider_url + 'pickup/', {'ticket_code': code, 'bag_count': 2}, format='json')
        self.assertEqual(correct.status_code, 200, correct.data)
        self.assertTrue(correct.data['delivery']['pickupVerifiedAt'])
        self.assertTrue(correct.data['contactAvailable'])
        self.assertNotIn(code, str(correct.data))
        self.assertEqual(DeliveryEvent.objects.filter(order=self.order, action='picked_up').count(), 1)

    def test_corrected_bag_count_reissues_ticket_only_before_pickup(self):
        original = self.handover().data['ticketCode']
        updated = self.handover(bag_count=3)
        self.assertEqual(updated.status_code, 200)
        code = updated.data['ticketCode']
        self.assertNotEqual(code, original)
        self.assertEqual(self.client.get(self.ticket_url).data['bagCount'], 3)
        self.assertEqual(self.rider_client.post(self.rider_url + 'pickup/', {'ticket_code': original, 'bag_count': 2}, format='json').status_code, 400)
        picked = self.rider_client.post(self.rider_url + 'pickup/', {'ticket_code': code, 'bag_count': 3}, format='json')
        self.assertEqual(picked.status_code, 200)
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.handover(bag_count=1).status_code, 400)

    def test_contact_opens_after_pickup_and_closes_after_verified_delivery(self):
        self.client.force_authenticate(self.customer)
        self.assertFalse(self.client.get(self.contact_url).data['canSend'])
        self.assertEqual(self.client.get(self.contact_url).data['rider']['phone'], '')
        message_id = str(uuid.uuid4())
        self.assertEqual(self.client.post(self.messages_url, {'body': 'Before pickup', 'client_message_id': message_id}, format='json').status_code, 400)
        self.client.force_authenticate(self.chef)
        self.pickup()
        self.client.force_authenticate(self.customer)
        self.assertTrue(self.client.get(self.contact_url).data['canSend'])
        sent = self.client.post(self.messages_url, {'body': 'Please use the side gate', 'client_message_id': message_id, 'senderRole': 'rider'}, format='json')
        self.assertEqual(sent.status_code, 201, sent.data)
        self.assertEqual(sent.data['senderRole'], 'customer')
        retry = self.client.post(self.messages_url, {'body': 'Please use the side gate', 'client_message_id': message_id}, format='json')
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.data['id'], sent.data['id'])
        self.assertEqual(self.client.post(self.messages_url, {'body': 'Changed text', 'client_message_id': message_id}, format='json').status_code, 409)
        reply = self.rider_client.post(self.rider_url + 'contact/messages/', {'body': 'On my way to the side gate', 'client_message_id': str(uuid.uuid4())}, format='json')
        self.assertEqual(reply.status_code, 201, reply.data)
        self.assertEqual(reply.data['senderRole'], 'rider')
        fresh = APIClient()
        fresh.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.customer).access_token}')
        self.assertEqual(len(fresh.get(self.messages_url).data['messages']), 2)
        self.rider_client.post(self.rider_url + 'arrive/')
        self.assertEqual(self.rider_client.post(self.rider_url + 'complete/', {'ticket_code': 'WRONG000', 'bag_count': 2, 'recipient_confirmed': True}, format='json').status_code, 400)
        self.assertEqual(self.rider_client.post(self.rider_url + 'complete/', {'ticket_code': self.code, 'bag_count': 2, 'recipient_confirmed': False}, format='json').status_code, 400)
        completed = self.rider_client.post(self.rider_url + 'complete/', {'ticket_code': self.code, 'bag_count': 2, 'recipient_confirmed': True}, format='json')
        self.assertEqual(completed.status_code, 200, completed.data)
        self.assertTrue(completed.data['delivery']['deliveryVerifiedAt'])
        self.assertFalse(fresh.get(self.contact_url).data['canSend'])
        self.assertEqual(fresh.post(self.messages_url, {'body': 'After delivery', 'client_message_id': str(uuid.uuid4())}, format='json').status_code, 400)
        self.assertEqual(len(fresh.get(self.messages_url).data['messages']), 2)

    def test_guest_private_credential_and_order_isolation(self):
        self.order.customer = None
        self.order.save(update_fields=['customer'])
        self.pickup()
        guest = APIClient()
        self.assertEqual(guest.get(self.contact_url).status_code, 404)
        self.assertEqual(guest.get(self.contact_url, HTTP_X_ORDER_CONTACT_TOKEN='wrong').status_code, 404)
        token = str(self.order.customer_chat_token)
        self.assertTrue(guest.get(self.contact_url, HTTP_X_ORDER_CONTACT_TOKEN=token).data['canSend'])
        send = guest.post(self.messages_url, {'body': 'Guest message', 'client_message_id': str(uuid.uuid4())}, format='json', HTTP_X_ORDER_CONTACT_TOKEN=token)
        self.assertEqual(send.status_code, 201, send.data)
        public = guest.get(f'/api/v1/orders/track/{self.order.order_number}/').data
        self.assertNotIn(token, str(public))
        self.assertNotIn(self.code, str(public))
        self.assertNotIn('Guest message', str(public))
        self.rider_client.force_authenticate(self.other_rider)
        self.assertEqual(self.rider_client.get(self.rider_url + 'contact/').status_code, 404)

    def test_other_customer_rider_and_read_only_dispatch_cannot_impersonate(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(self.contact_url).status_code, 404)
        self.assertEqual(self.client.get(self.ticket_url).status_code, 403)
        self.assertEqual(self.rider_client.get(self.ticket_url).status_code, 403)
        self.client.force_authenticate(self.manager)
        dispatch = f'/api/v1/orders/{self.order.id}/delivery/contact/'
        self.assertFalse(self.client.get(dispatch).data['canSend'])
        self.assertEqual(self.client.post(dispatch + 'messages/', {'body': 'Impersonation'}, format='json').status_code, 405)
        self.assertEqual(self.client.patch(f'/api/v1/orders/{self.order.id}/update_status/', {'status': 'out_for_delivery'}, format='json').status_code, 400)

    def test_reassignment_invalidates_the_old_bag_ticket(self):
        old = self.handover().data['ticketCode']
        self.rider_client.post(self.rider_url + 'decline/', {'note': 'Vehicle unavailable'}, format='json')
        job = DeliveryJob.objects.get(order=self.order)
        self.assertEqual(job.handover_code, '')
        self.assertIsNone(job.handed_over_at)
        self.assertNotIn(old, str(self.client.get(self.ticket_url).data))

    def test_message_cursor_paginates_saved_history(self):
        self.pickup()
        DeliveryMessage.objects.bulk_create([DeliveryMessage(order=self.order, rider=self.rider, sender=self.customer, sender_role='customer', sender_name='Ticket Buyer', body=f'Message {index}', client_message_id=uuid.uuid4()) for index in range(102)])
        self.client.force_authenticate(self.customer)
        first = self.client.get(self.messages_url).data
        self.assertTrue(first['hasMore'])
        self.assertEqual(len(first['messages']), 100)
        second = self.client.get(self.messages_url, {'after_id': first['nextAfterId']}).data
        self.assertFalse(second['hasMore'])
        self.assertEqual(len(second['messages']), 2)
        self.assertEqual(self.client.get(self.messages_url, {'after_id': 'bad'}).status_code, 400)
