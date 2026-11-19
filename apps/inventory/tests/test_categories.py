from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import InventoryCategory, InventoryItem

User = get_user_model()


class InventoryCategoryAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username='inv-manager',
            email='inv-manager@example.com',
            role=User.Role.MANAGER,
        )
        cls.staff = User.objects.create_user(
            username='inv-staff',
            email='inv-staff@example.com',
            role=User.Role.STAFF,
        )
        cls.customer = User.objects.create_user(
            username='inv-customer',
            email='inv-customer@example.com',
            role=User.Role.CUSTOMER,
        )

        cls.meat_cat = InventoryCategory.objects.create(
            name='Meat & Poultry',
            description='Fresh chicken, lamb, and beef cuts',
            is_active=True,
        )
        cls.spice_cat = InventoryCategory.objects.create(
            name='Spices & Seasoning',
            description='Authentic whole and ground spices',
            is_active=True,
        )
        cls.dairy_cat = InventoryCategory.objects.create(
            name='Dairy',
            description='Milk, cream, paneer, and yoghurt',
            is_active=False,
        )

        # Create sample items for count test
        cls.chicken = InventoryItem.objects.create(
            name='Free-Range Chicken Breast',
            category='Meat & Poultry',
            category_ref=cls.meat_cat,
            current_stock=Decimal('25.00'),
            minimum_stock=Decimal('10.00'),
            unit='kg',
            supplier='Valley Farm',
        )

    def setUp(self):
        self.list_url = reverse('inventory-category-list')

    def test_unauthenticated_cannot_list_categories(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_cannot_list_categories(self):
        self.client.force_authenticate(user=self.customer)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_list_categories(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify pagination or list structure
        data = response.data['results'] if 'results' in response.data else response.data
        self.assertGreaterEqual(len(data), 3)

        # Verify fields
        first = next(c for c in data if c['id'] == self.meat_cat.id)
        self.assertEqual(first['name'], 'Meat & Poultry')
        self.assertEqual(first['slug'], 'meat-poultry')
        self.assertEqual(first['itemsCount'], 1)
        self.assertTrue(first['is_active'])

    def test_manager_can_create_category(self):
        self.client.force_authenticate(user=self.manager)
        payload = {
            'name': 'Baking & Pantry',
            'description': 'Flour, sugar, baking soda, and yeast',
            'is_active': True,
        }
        response = self.client.post(self.list_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Baking & Pantry')
        self.assertEqual(response.data['slug'], 'baking-pantry')
        self.assertEqual(response.data['itemsCount'], 0)
        self.assertTrue(InventoryCategory.objects.filter(name='Baking & Pantry').exists())

    def test_duplicate_category_name_rejected(self):
        self.client.force_authenticate(user=self.manager)
        payload = {
            'name': 'meat & poultry',  # Case insensitive duplicate
            'description': 'Another description',
        }
        response = self.client.post(self.list_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)

    def test_blank_category_name_rejected(self):
        self.client.force_authenticate(user=self.manager)
        payload = {'name': '   '}
        response = self.client.post(self.list_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)

    def test_retrieve_category_detail(self):
        self.client.force_authenticate(user=self.staff)
        url = reverse('inventory-category-detail', kwargs={'pk': self.meat_cat.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Meat & Poultry')
        self.assertEqual(response.data['itemsCount'], 1)

    def test_manager_can_update_category(self):
        self.client.force_authenticate(user=self.manager)
        url = reverse('inventory-category-detail', kwargs={'pk': self.spice_cat.pk})
        response = self.client.patch(url, {'description': 'Updated spice description', 'is_active': False}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['description'], 'Updated spice description')
        self.assertFalse(response.data['is_active'])

        self.spice_cat.refresh_from_db()
        self.assertEqual(self.spice_cat.description, 'Updated spice description')
        self.assertFalse(self.spice_cat.is_active)

    def test_manager_can_delete_category(self):
        self.client.force_authenticate(user=self.manager)
        to_delete = InventoryCategory.objects.create(name='Disposable Packaging')
        url = reverse('inventory-category-detail', kwargs={'pk': to_delete.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(InventoryCategory.objects.filter(pk=to_delete.pk).exists())
