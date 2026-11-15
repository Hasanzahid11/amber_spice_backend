from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

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

    def create_address(self, label='home', **extra):
        return self.client.post(reverse('user-address-list'), {
            'label': label, 'address_line1': f'{label.title()} Street', 'city': 'Carlow',
            'postal_code': 'R93 TEST', **extra,
        }, format='json')

    def test_one_home_one_work_and_multiple_other_addresses(self):
        for label in ('home', 'work', 'other', 'other'):
            self.assertEqual(self.create_address(label).status_code, status.HTTP_201_CREATED)
        for label in ('home', 'work'):
            duplicate = self.create_address(label)
            self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn('label', duplicate.data)
        self.assertEqual(UserAddress.objects.filter(user=self.user).count(), 4)

    def test_edit_validation_and_reload_with_fresh_jwt_client(self):
        home = self.create_address().data
        work = self.create_address('work').data
        home_url = reverse('user-address-detail', kwargs={'pk': home['id']})
        update = self.client.patch(home_url, {
            'address_line1': 'Updated Home Street', 'postal_code': 'R93 SAVE', 'delivery_instructions': 'Ring twice',
        }, format='json')
        self.assertEqual(update.status_code, status.HTTP_200_OK)
        conflict = self.client.patch(reverse('user-address-detail', kwargs={'pk': work['id']}), {'label': 'home'}, format='json')
        self.assertEqual(conflict.status_code, status.HTTP_400_BAD_REQUEST)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.user).access_token}')
        reloaded = client.get(home_url)
        self.assertEqual(reloaded.data['address_line1'], 'Updated Home Street')
        self.assertEqual(reloaded.data['postal_code'], 'R93 SAVE')
        profile = client.get(reverse('profile_me')).data
        self.assertEqual(len(profile['savedAddresses']), 2)
        self.assertEqual(next(item for item in profile['savedAddresses'] if item['label'] == 'home')['delivery_instructions'], 'Ring twice')
        deleted = client.delete(home_url)
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(client.get(home_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(len(client.get(reverse('profile_me')).data['savedAddresses']), 1)

    def test_address_operations_require_authentication_and_owner(self):
        home = self.create_address().data
        other = User.objects.create_user(username='other_address_owner', password='Password123!')
        client = APIClient()
        self.assertEqual(client.get(reverse('user-address-list')).status_code, status.HTTP_401_UNAUTHORIZED)
        client.force_authenticate(other)
        url = reverse('user-address-detail', kwargs={'pk': home['id']})
        self.assertEqual(client.get(url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(client.patch(url, {'address_line1': 'Unauthorized'}, format='json').status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(client.delete(url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(client.post(reverse('user-address-set-default', kwargs={'pk': home['id']})).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.create_address('work').status_code, status.HTTP_201_CREATED)
        self.assertEqual(client.post(reverse('user-address-list'), {'label': 'home', 'address_line1': 'Other Home', 'postal_code': 'R93 OWN'}, format='json').status_code, status.HTTP_201_CREATED)

    def test_can_delete_last_address_and_checkout_choices_become_empty(self):
        address = self.create_address().data
        self.assertEqual(self.client.delete(reverse('user-address-detail', kwargs={'pk': address['id']})).status_code, status.HTTP_204_NO_CONTENT)
        profile = self.client.get(reverse('profile_me')).data
        self.assertEqual(profile['savedAddresses'], [])
        self.assertIsNone(profile['defaultAddress'])

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

