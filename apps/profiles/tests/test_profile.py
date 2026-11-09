from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

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


