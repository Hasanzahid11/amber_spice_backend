from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.constants import DEFAULT_ROLE_PERMISSIONS
from apps.accounts.models import RolePermissionConfig
from apps.menu.models import Category, Dish

User = get_user_model()


class AuthAndRBACGoldStandardTests(APITestCase):
    def setUp(self):
        # Setup role permission configurations
        for role_key, perms in DEFAULT_ROLE_PERMISSIONS.items():
            RolePermissionConfig.objects.get_or_create(
                role=role_key,
                defaults={'name': role_key.title(), 'permissions': perms}
            )

        # 1. Admin/Owner
        self.admin_user = User.objects.create_superuser(
            username='owner_admin',
            email='owner@restaurant.com',
            password='password123',
            role=User.Role.ADMIN
        )

        # 2. Manager
        self.manager_user = User.objects.create_user(
            username='manager_user',
            email='manager@restaurant.com',
            password='password123',
            role=User.Role.MANAGER
        )

        # 3. Kitchen Staff
        self.kitchen_user = User.objects.create_user(
            username='chef_user',
            email='chef@restaurant.com',
            password='password123',
            role=User.Role.KITCHEN_STAFF
        )

        # 4. Delivery Staff
        self.delivery_user = User.objects.create_user(
            username='driver_user',
            email='driver@restaurant.com',
            password='password123',
            role=User.Role.DELIVERY_STAFF
        )

        # 5. Cashier / Front Staff
        self.cashier_user = User.objects.create_user(
            username='cashier_user',
            email='cashier@restaurant.com',
            password='password123',
            role=User.Role.CASHIER_FRONT
        )

        # 6. Customer
        self.customer_user = User.objects.create_user(
            username='customer_jane',
            email='jane@example.com',
            password='password123',
            role=User.Role.CUSTOMER
        )

        # Sample Category & Dish
        self.category = Category.objects.create(name='Main Course', slug='main-course')
        self.dish = Dish.objects.create(
            category=self.category,
            name='Chicken Tikka Masala',
            price=15.00,
            is_available=True
        )

    def test_customer_registration_success(self):
        url = reverse('auth_register')
        payload = {
            'username': 'newcustomer',
            'email': 'newcustomer@test.com',
            'first_name': 'New',
            'last_name': 'Customer',
            'phone': '+1234567890',
            'password': 'SecurePassword@123',
            'password_confirm': 'SecurePassword@123',
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['role'], 'customer')

    def test_customer_registration_with_single_full_name_and_no_last_name(self):
        url = reverse('auth_register')
        payload = {
            'email': 'singlename@test.com',
            'full_name': 'Hridoy Developer',
            'phone': '+353871112222',
            'password': 'SecurePassword@123',
            'confirm_password': 'SecurePassword@123',
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', response.data)
        self.assertEqual(response.data['user']['fullName'], 'Hridoy Developer')

    def test_login_invalid_credentials_returns_clean_detail(self):
        url = reverse('auth_login')
        response = self.client.post(url, {'email': 'invalid@test.com', 'password': 'wrongpassword'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)
        detail_msg = response.data['detail'][0] if isinstance(response.data['detail'], list) else response.data['detail']
        self.assertIn('Invalid email or password', str(detail_msg))

    def test_login_with_username_and_email(self):
        url = reverse('auth_login')

        # Login via username
        res1 = self.client.post(url, {'username': 'manager_user', 'password': 'password123'})
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertIn('access', res1.data)
        self.assertEqual(res1.data['user']['role'], 'manager')

        # Login via email field directly (as sent by frontend forms)
        res2 = self.client.post(url, {'email': 'manager@restaurant.com', 'password': 'password123'}, format='json')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertIn('access', res2.data)
        self.assertEqual(res2.data['user']['email'], 'manager@restaurant.com')

    def test_user_permissions_resolution(self):
        # Kitchen Staff
        self.assertTrue(self.kitchen_user.has_restaurant_permission('kitchen:view_orders'))
        self.assertTrue(self.kitchen_user.has_restaurant_permission('menu:toggle_availability'))
        self.assertFalse(self.kitchen_user.has_restaurant_permission('reports:view'))
        self.assertFalse(self.kitchen_user.has_restaurant_permission('inventory:manage'))

        # Delivery Staff
        self.assertTrue(self.delivery_user.has_restaurant_permission('deliveries:view_assigned'))
        self.assertFalse(self.delivery_user.has_restaurant_permission('kitchen:view_orders'))
        self.assertFalse(self.delivery_user.has_restaurant_permission('reports:view'))

        # Manager
        self.assertTrue(self.manager_user.has_restaurant_permission('reports:view'))
        self.assertTrue(self.manager_user.has_restaurant_permission('inventory:manage'))
        self.assertTrue(self.manager_user.has_restaurant_permission('staff:manage'))

        # Admin / Owner has full access
        self.assertTrue(self.admin_user.has_restaurant_permission('settings:manage'))
        self.assertTrue(self.admin_user.has_restaurant_permission('reports:view'))

    def test_kitchen_staff_can_toggle_dish_availability(self):
        self.client.force_authenticate(user=self.kitchen_user)
        url = f"/api/v1/menu/dishes/{self.dish.id}/toggle-availability/"

        # Toggle to unavailable
        res = self.client.patch(url, {'is_available': False}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.dish.refresh_from_db()
        self.assertFalse(self.dish.is_available)

    def test_customer_cannot_access_analytics_or_inventory(self):
        self.client.force_authenticate(user=self.customer_user)

        res_analytics = self.client.get('/api/v1/analytics/summary/')
        self.assertEqual(res_analytics.status_code, status.HTTP_403_FORBIDDEN)

        res_inventory = self.client.get('/api/v1/inventory/items/')
        self.assertEqual(res_inventory.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_access_analytics(self):
        self.client.force_authenticate(user=self.manager_user)
        res = self.client.get('/api/v1/analytics/summary/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('totalRevenue', res.data)

    def test_admin_can_configure_role_permissions(self):
        self.client.force_authenticate(user=self.admin_user)
        config = RolePermissionConfig.objects.get(role='kitchen_staff')
        url = f"/api/v1/auth/roles-config/{config.id}/"

        new_perms = ['kitchen:view_orders', 'kitchen:update_status', 'menu:toggle_availability', 'menu:view']
        res = self.client.patch(url, {'permissions': new_perms}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        config.refresh_from_db()
        self.assertIn('menu:view', config.permissions)
