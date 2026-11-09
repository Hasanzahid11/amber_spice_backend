from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.profiles.models import UserAddress

User = get_user_model()


class AddressGoldStandardTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='address_tester',
            email='address@example.com',
            password='Password123!',
            first_name='Address',
            last_name='Tester',
            role=User.Role.CUSTOMER
        )
        self.client.force_authenticate(user=self.user)

    def test_create_address_and_auto_default(self):
        url = reverse('user-address-list')
        payload = {
            'label': 'home',
            'recipient_name': 'Address Tester',
            'recipient_phone': '+353871112222',
            'address_line1': '14 Grafton Street',
            'city': 'Dublin',
            'county_or_state': 'Co. Dublin',
            'postal_code': 'D02 X285',
            'delivery_instructions': 'Second floor, buzz 2B',
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['is_default'])
        self.assertEqual(UserAddress.objects.filter(user=self.user).count(), 1)

    def test_set_new_default_address(self):
        # Create first address (default)
        addr1 = UserAddress.objects.create(
            user=self.user,
            label='home',
            address_line1='10 Main Street',
            postal_code='D01 AA01',
            is_default=True
        )
        # Create second address
        addr2 = UserAddress.objects.create(
            user=self.user,
            label='work',
            address_line1='5 Grand Canal Dock',
            postal_code='D02 BB02',
            is_default=False
        )

        url = reverse('user-address-set-default', kwargs={'pk': addr2.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        addr1.refresh_from_db()
        addr2.refresh_from_db()
        self.assertFalse(addr1.is_default)
        self.assertTrue(addr2.is_default)

    def test_delete_default_promotes_next_address(self):
        addr1 = UserAddress.objects.create(
            user=self.user,
            label='home',
            address_line1='10 Main Street',
            postal_code='D01 AA01',
            is_default=True
        )
        addr2 = UserAddress.objects.create(
            user=self.user,
            label='work',
            address_line1='5 Grand Canal Dock',
            postal_code='D02 BB02',
            is_default=False
        )

        url = reverse('user-address-detail', kwargs={'pk': addr1.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        addr2.refresh_from_db()
        self.assertTrue(addr2.is_default)

