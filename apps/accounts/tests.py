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
            phone='+353871234567',
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

    def test_login_with_username_and_email(self):
        url = reverse('auth_login')

        # Login via username
        res1 = self.client.post(url, {'username': 'manager_user', 'password': 'password123'})
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertIn('access', res1.data)
        self.assertEqual(res1.data['user']['role'], 'manager')

        # Login via email
        res2 = self.client.post(url, {'username': 'manager@restaurant.com', 'password': 'password123'})
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertIn('access', res2.data)

        # Login via Irish phone in international format
        res3 = self.client.post(url, {'username': '+353871234567', 'password': 'password123'})
        self.assertEqual(res3.status_code, status.HTTP_200_OK)
        self.assertIn('access', res3.data)
        self.assertEqual(res3.data['user']['username'], 'customer_jane')

        # Login via Irish phone in local format (0871234567)
        res4 = self.client.post(url, {'username': '0871234567', 'password': 'password123'})
        self.assertEqual(res4.status_code, status.HTTP_200_OK)
        self.assertIn('access', res4.data)
        self.assertEqual(res4.data['user']['username'], 'customer_jane')

        # Login via Irish phone formatted with spaces (+353 87 123 4567)
        res5 = self.client.post(url, {'username': '+353 87 123 4567', 'password': 'password123'})
        self.assertEqual(res5.status_code, status.HTTP_200_OK)
        self.assertIn('access', res5.data)

        # Login via dedicated 'phone' payload field
        res6 = self.client.post(url, {'phone': '087 123 4567', 'password': 'password123'})
        self.assertEqual(res6.status_code, status.HTTP_200_OK)
        self.assertIn('access', res6.data)

        # Login via dedicated 'email' payload field
        res7 = self.client.post(url, {'email': 'jane@example.com', 'password': 'password123'})
        self.assertEqual(res7.status_code, status.HTTP_200_OK)
        self.assertIn('access', res7.data)

    def test_customer_registration_phone_only_irish(self):
        url = reverse('auth_register')
        payload = {
            'phone': '0879876543',
            'first_name': 'Liam',
            'last_name': 'Murphy',
            'password': 'SecureIrishPassword@123',
            'password_confirm': 'SecureIrishPassword@123',
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', response.data)
        self.assertEqual(response.data['user']['role'], 'customer')
        self.assertEqual(response.data['user']['phone'], '+353879876543')
        self.assertIsNone(response.data['user']['email'])

        # Verify new user can immediately log in with local phone or intl phone
        login_url = reverse('auth_login')
        res_login = self.client.post(login_url, {
            'username': '0879876543',
            'password': 'SecureIrishPassword@123'
        })
        self.assertEqual(res_login.status_code, status.HTTP_200_OK)

    def test_customer_registration_email_only(self):
        url = reverse('auth_register')
        payload = {
            'email': 'emailonly@example.com',
            'first_name': 'Sinead',
            'last_name': 'O\'Connor',
            'password': 'SecureIrishPassword@123',
            'password_confirm': 'SecureIrishPassword@123',
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user']['email'], 'emailonly@example.com')
        self.assertIsNone(response.data['user']['phone'])

        # Verify new user can log in with email
        login_url = reverse('auth_login')
        res_login = self.client.post(login_url, {
            'username': 'emailonly@example.com',
            'password': 'SecureIrishPassword@123'
        })
        self.assertEqual(res_login.status_code, status.HTTP_200_OK)

    def test_customer_registration_fails_without_phone_and_email(self):
        url = reverse('auth_register')
        payload = {
            'first_name': 'No',
            'last_name': 'Contact',
            'password': 'SecurePassword@123',
            'password_confirm': 'SecurePassword@123',
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_customer_registration_duplicate_phone_fails(self):
        url = reverse('auth_register')
        payload = {
            'phone': '0871234567',  # Jane's phone (+353871234567)
            'first_name': 'Duplicate',
            'last_name': 'User',
            'password': 'SecurePassword@123',
            'password_confirm': 'SecurePassword@123',
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone', response.data)

    def test_customer_registration_duplicate_email_fails(self):
        url = reverse('auth_register')
        payload = {
            'email': 'jane@example.com',  # Jane's email
            'first_name': 'Duplicate',
            'last_name': 'User',
            'password': 'SecurePassword@123',
            'password_confirm': 'SecurePassword@123',
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

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

        # Test reset to defaults
        reset_url = f"/api/v1/auth/roles-config/{config.id}/reset/"
        res_reset = self.client.post(reset_url)
        self.assertEqual(res_reset.status_code, status.HTTP_200_OK)
        config.refresh_from_db()
        self.assertNotIn('menu:view', config.permissions)

        # Test lookup by role
        by_role_url = "/api/v1/auth/roles-config/by-role/?role=kitchen_staff"
        res_by_role = self.client.get(by_role_url)
        self.assertEqual(res_by_role.status_code, status.HTTP_200_OK)
        self.assertEqual(res_by_role.data['role'], 'kitchen_staff')

        # Test rejecting invalid permission code
        res_invalid = self.client.patch(url, {'permissions': ['fake:permission']}, format='json')
        self.assertEqual(res_invalid.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cashier_front_staff_access_levels(self):
        self.client.force_authenticate(user=self.cashier_user)

        # Can view customer directory
        res_customers = self.client.get('/api/v1/auth/customers/')
        self.assertEqual(res_customers.status_code, status.HTTP_200_OK)

        # Cannot view analytics/reports
        res_reports = self.client.get('/api/v1/analytics/summary/')
        self.assertEqual(res_reports.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot manage inventory
        res_inv = self.client.get('/api/v1/inventory/items/')
        self.assertEqual(res_inv.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot configure roles
        config = RolePermissionConfig.objects.first()
        res_cfg = self.client.patch(f"/api/v1/auth/roles-config/{config.id}/", {'permissions': []})
        self.assertEqual(res_cfg.status_code, status.HTTP_403_FORBIDDEN)

    def test_delivery_staff_access_levels(self):
        self.client.force_authenticate(user=self.delivery_user)

        # Cannot view kitchen KDS
        res_kitchen = self.client.get('/api/v1/orders/kitchen/')
        self.assertEqual(res_kitchen.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot view analytics
        res_reports = self.client.get('/api/v1/analytics/summary/')
        self.assertEqual(res_reports.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot view customer directory
        res_cust = self.client.get('/api/v1/auth/customers/')
        self.assertEqual(res_cust.status_code, status.HTTP_403_FORBIDDEN)

    def test_kitchen_staff_access_levels(self):
        self.client.force_authenticate(user=self.kitchen_user)

        # Cannot view deliveries
        res_deliv = self.client.get('/api/v1/orders/deliveries/')
        self.assertEqual(res_deliv.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot view customer directory
        res_cust = self.client.get('/api/v1/auth/customers/')
        self.assertEqual(res_cust.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot view reports
        res_rep = self.client.get('/api/v1/analytics/summary/')
        self.assertEqual(res_rep.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_custom_permission_overrides(self):
        from apps.accounts.models import UserCustomPermission

        # Initially kitchen user has no reports:view
        self.assertFalse(self.kitchen_user.has_restaurant_permission('reports:view'))

        # Grant specific permission to kitchen user
        UserCustomPermission.objects.create(
            user=self.kitchen_user,
            granted_permissions=['reports:view'],
            revoked_permissions=['menu:toggle_availability']
        )
        self.kitchen_user.refresh_from_db()

        # Granted permission is now active
        self.assertTrue(self.kitchen_user.has_restaurant_permission('reports:view'))
        # Revoked permission is now inactive
        self.assertFalse(self.kitchen_user.has_restaurant_permission('menu:toggle_availability'))
