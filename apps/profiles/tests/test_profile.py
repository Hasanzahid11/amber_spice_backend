from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.generators import SchemaGenerator

from apps.profiles.models import UserProfile, UserPreferences

User = get_user_model()


class ProfileGoldStandardTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='dublin_customer',
            email='dublin@example.com',
            password='Password123!',
            first_name='Dublin',
            last_name='Eater',
            role=User.Role.CUSTOMER
        )
        self.client.force_authenticate(user=self.user)

    def test_profile_auto_created_by_signals(self):
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())
        self.assertTrue(UserPreferences.objects.filter(user=self.user).exists())

    def test_get_current_user_profile(self):
        url = reverse('profile_me')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'dublin_customer')
        self.assertEqual(response.data['loyalty_tier'], 'bronze')
        self.assertIn('completionPercentage', response.data)

    def test_update_profile_and_user_fields(self):
        url = reverse('profile_me')
        payload = {
            'name': 'Sarah Connor',
            'email': 'sarah.updated@example.com',
            'phone': '+353871234567',
            'bio': 'Lover of spicy Indian curries in Dublin',
            'default_delivery_instructions': 'Leave at gate code 1234',
        }
        response = self.client.patch(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.get_full_name(), 'Sarah Connor')
        self.assertEqual(self.user.email, 'sarah.updated@example.com')
        self.assertEqual(self.user.phone, '+353871234567')
        self.assertEqual(self.user.profile.bio, 'Lover of spicy Indian curries in Dublin')

    def test_update_preferences(self):
        url = reverse('profile_preferences')
        payload = {
            'is_halal_only': True,
            'is_vegetarian': True,
            'spice_tolerance': 'hot',
            'include_plastic_cutlery': False,
        }
        response = self.client.patch(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.preferences.refresh_from_db()
        self.assertTrue(self.user.preferences.is_halal_only)
        self.assertTrue(self.user.preferences.is_vegetarian)
        self.assertEqual(self.user.preferences.spice_tolerance, 'hot')

    def test_checkout_details_survive_a_fresh_authenticated_read(self):
        profile_url = reverse('profile_me')
        update = self.client.patch(profile_url, {
            'name': 'Saved Customer', 'phone': '+353871112222',
            'email': 'saved@example.com', 'default_delivery_instructions': 'Call on arrival',
        }, format='json')
        self.assertEqual(update.status_code, status.HTTP_200_OK)
        address = self.client.post(reverse('user-address-list'), {
            'label': 'home', 'address_line1': '12 Saved Street', 'address_line2': 'Flat 2',
            'city': 'Carlow', 'county_or_state': 'Co. Carlow', 'postal_code': 'R93 TEST',
            'delivery_instructions': 'Ring the buzzer', 'is_default': True,
        }, format='json')
        self.assertEqual(address.status_code, status.HTTP_201_CREATED)

        # A fresh client/JWT represents a page reload without browser form state.
        fresh_client = APIClient()
        fresh_client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.user).access_token}')
        reloaded = fresh_client.get(profile_url)
        self.assertEqual(reloaded.status_code, status.HTTP_200_OK)
        self.assertEqual(reloaded.data['fullName'], 'Saved Customer')
        self.assertEqual(reloaded.data['phone'], '+353871112222')
        self.assertEqual(reloaded.data['email'], 'saved@example.com')
        self.assertEqual(reloaded.data['defaultAddress']['id'], address.data['id'])
        self.assertEqual(reloaded.data['defaultAddress']['postal_code'], 'R93 TEST')
        self.assertEqual(reloaded.data['defaultAddress']['delivery_instructions'], 'Ring the buzzer')

        other_user = User.objects.create_user(username='other_checkout', password='Password123!')
        fresh_client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(other_user).access_token}')
        other_profile = fresh_client.get(profile_url)
        self.assertIsNone(other_profile.data['defaultAddress'])
        self.assertNotEqual(other_profile.data['fullName'], 'Saved Customer')

    def test_checkout_profile_schema_exposes_properties_and_authentication(self):
        schema = SchemaGenerator().get_schema(public=True)
        profile_path = schema['paths']['/api/v1/profiles/me/']
        self.assertTrue(profile_path['get']['security'])
        self.assertIn('requestBody', profile_path['patch'])
        profile_schema = schema['components']['schemas']['CustomerProfile']
        self.assertIn('defaultAddress', profile_schema['properties'])
        self.assertIn('UserAddress', str(profile_schema['properties']['defaultAddress']))
        self.assertEqual(profile_schema['properties']['savedAddresses']['type'], 'array')
        address_paths = schema['paths']['/api/v1/profiles/addresses/']
        self.assertTrue(address_paths['post']['security'])
        self.assertIn('requestBody', address_paths['post'])
        self.assertIn('patch', schema['paths']['/api/v1/profiles/addresses/{id}/'])
        self.assertIn('delete', schema['paths']['/api/v1/profiles/addresses/{id}/'])
        self.assertIn('/api/v1/profiles/addresses/', schema['paths'])

    def test_updated_email_becomes_new_login_email(self):
        # 1. Update email via profile PATCH
        url = reverse('profile_me')
        res_update = self.client.patch(
            url,
            {'email': 'dublin.new@example.com'},
            format='json'
        )
        self.assertEqual(res_update.status_code, status.HTTP_200_OK)
        self.assertEqual(res_update.data['email'], 'dublin.new@example.com')

        # 2. Logout current session
        self.client.logout()

        # 3. Login with NEW email should succeed
        login_url = reverse('auth_login')
        res_login_new = self.client.post(
            login_url,
            {'email': 'dublin.new@example.com', 'password': 'Password123!'},
            format='json'
        )
        self.assertEqual(res_login_new.status_code, status.HTTP_200_OK)
        self.assertIn('access', res_login_new.data)
        self.assertEqual(res_login_new.data['user']['email'], 'dublin.new@example.com')

        # 4. Login with OLD email must fail
        res_login_old = self.client.post(
            login_url,
            {'email': 'dublin@example.com', 'password': 'Password123!'},
            format='json'
        )
        self.assertEqual(res_login_old.status_code, status.HTTP_400_BAD_REQUEST)


