from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import InventoryCategory, InventoryItem

User = get_user_model()


class InventoryItemAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username='item-manager',
            email='item-manager@example.com',
            role=User.Role.MANAGER,
        )
        cls.staff = User.objects.create_user(
            username='item-staff',
            email='item-staff@example.com',
            role=User.Role.STAFF,
        )
        cls.category = InventoryCategory.objects.create(
            name='Meat & Poultry',
            description='Fresh meat cuts',
        )
        cls.item = InventoryItem.objects.create(
            name='Chicken Thighs',
            category='Meat & Poultry',
            category_ref=cls.category,
            current_stock=Decimal('15.00'),
            minimum_stock=Decimal('20.00'),
            unit='kg',
            supplier='Farm Direct',
        )

    def setUp(self):
        self.list_url = reverse('inventory-item-list')
        self.detail_url = reverse('inventory-item-detail', kwargs={'pk': self.item.pk})

    def test_list_items_staff(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data['results'] if 'results' in response.data else response.data
        self.assertGreaterEqual(len(data), 1)
        first = data[0]
        self.assertIn('name', first)
        self.assertIn('currentStock', first)
        self.assertIn('minimumStock', first)

    def test_create_item_manager(self):
        self.client.force_authenticate(user=self.manager)
        payload = {
            'name': 'Garam Masala Blend',
            'category': 'Spices & Seasoning',
            'currentStock': '5.00',
            'minimumStock': '2.00',
            'unit': 'kg',
            'supplier': 'Spice Route Ltd',
        }
        response = self.client.post(self.list_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Garam Masala Blend')
        self.assertEqual(Decimal(str(response.data['currentStock'])), Decimal('5.00'))

    def test_update_item_manager(self):
        self.client.force_authenticate(user=self.manager)
        payload = {
            'name': 'Chicken Thighs (Boneless)',
            'minimumStock': '25.00',
        }
        response = self.client.patch(self.detail_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, 'Chicken Thighs (Boneless)')
        self.assertEqual(self.item.minimum_stock, Decimal('25.00'))

    def test_delete_item_manager(self):
        self.client.force_authenticate(user=self.manager)
        to_delete = InventoryItem.objects.create(
            name='Temporary Item',
            category='Pantry',
            current_stock=Decimal('1.00'),
            minimum_stock=Decimal('1.00'),
        )
        url = reverse('inventory-item-detail', kwargs={'pk': to_delete.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(InventoryItem.objects.filter(pk=to_delete.pk).exists())

    def test_restock_item_manager(self):
        self.client.force_authenticate(user=self.manager)
        url = reverse('inventory-item-restock', kwargs={'pk': self.item.pk})
        response = self.client.post(url, {'amount': '10.50'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal('25.50'))
