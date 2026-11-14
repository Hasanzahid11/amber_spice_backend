from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.test import APITestCase

from apps.accounts.models import UserCustomPermission
from ..models import Category, Dish

User = get_user_model()


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'menu-category-api-tests',
    },
})
class CategoryAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username='menu-manager', email='menu-manager@example.com', role=User.Role.MANAGER,
        )
        cls.customer = User.objects.create_user(
            username='menu-customer', email='menu-customer@example.com', role=User.Role.CUSTOMER,
        )
        cls.chef = User.objects.create_user(
            username='menu-chef', email='menu-chef@example.com', role=User.Role.CHEF,
        )
        cls.biryani = Category.objects.create(name='Biryani', order=2)
        cls.curries = Category.objects.create(name='Curries', order=1)
        cls.hidden = Category.objects.create(name='Seasonal', is_active=False)
        cls.dish = Dish.objects.create(
            category=cls.biryani, name='Chicken Biryani', price='15.50',
            is_popular=True, is_bestseller=True,
        )
        Dish.objects.create(category=cls.biryani, name='Sold Out Biryani', price='18.00', is_available=False)
        cls.hidden_dish = Dish.objects.create(
            category=cls.hidden, name='Seasonal Special', price='20.00',
            is_popular=True, is_bestseller=True,
        )

    def setUp(self):
        cache.clear()
        self.list_url = reverse('category-list')

    def tearDown(self):
        cache.clear()

    def detail_url(self, category):
        return reverse('category-detail', kwargs={'pk': category.pk})

    def as_manager(self):
        self.client.force_authenticate(user=self.manager)

    def test_public_list_contains_only_active_categories_in_display_order(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual([row['name'] for row in response.data['results']], ['Curries', 'Biryani'])
        self.assertEqual(response.data['results'][1]['dishCount'], 1)
        self.assertIn('created_at', response.data['results'][0])

    def test_public_cannot_retrieve_or_filter_into_inactive_category(self):
        self.assertEqual(self.client.get(self.detail_url(self.hidden)).status_code, status.HTTP_404_NOT_FOUND)
        response = self.client.get(self.list_url, {'is_active': 'false'})
        self.assertEqual(response.data['count'], 0)

    def test_menu_manager_can_list_edit_and_reactivate_inactive_category(self):
        self.as_manager()
        self.assertEqual(self.client.get(self.list_url).data['count'], 3)
        filtered = self.client.get(self.list_url, {'is_active': 'false'})
        self.assertEqual([row['id'] for row in filtered.data['results']], [self.hidden.pk])
        response = self.client.patch(self.detail_url(self.hidden), {'is_active': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.detail_url(self.hidden)).status_code, status.HTTP_200_OK)

    def test_only_name_is_required_and_slug_is_generated(self):
        self.as_manager()
        response = self.client.post(self.list_url, {'name': '  Breads & Naan  '}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Breads & Naan')
        self.assertEqual(response.data['slug'], 'breads-naan')
        self.assertEqual(response.data['order'], 0)
        self.assertTrue(response.data['is_active'])
        self.assertEqual(response.data['dishCount'], 0)
        self.assertIsNone(response.data['imageUrl'])

    def test_create_accepts_all_writable_properties_and_persists_image(self):
        self.as_manager()
        payload = {
            'name': 'Grill', 'slug': 'GRILLED-FOOD', 'description': 'From the charcoal grill',
            'imageUrl': 'https://example.com/menu/grill.webp', 'order': 4, 'is_active': False,
        }
        response = self.client.post(self.list_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        saved = Category.objects.get(pk=response.data['id'])
        self.assertEqual(saved.slug, 'grilled-food')
        self.assertEqual(saved.image_url, payload['imageUrl'])
        self.assertFalse(saved.is_active)

    def test_invalid_fields_and_case_insensitive_duplicates_return_validation_errors(self):
        self.as_manager()
        invalid = [
            ({}, 'name'), ({'name': '   '}, 'name'), ({'name': 'x' * 101}, 'name'),
            ({'name': 'biryani'}, 'name'),
            ({'name': 'New', 'slug': 'BIRYANI'}, 'slug'),
            ({'name': 'New', 'slug': 'not a slug'}, 'slug'),
            ({'name': 'New', 'order': -1}, 'order'),
            ({'name': 'New', 'imageUrl': 'not-an-image-url'}, 'imageUrl'),
            ({'name': 'New', 'imageUrl': 'ftp://example.com/menu.jpg'}, 'imageUrl'),
        ]
        for payload, field in invalid:
            with self.subTest(payload=payload):
                response = self.client.post(self.list_url, payload, format='json')
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)
        self.assertEqual(Category.objects.count(), 3)

    def test_auto_slug_collision_gets_suffix_and_non_ascii_name_gets_nonempty_slug(self):
        self.as_manager()
        first = self.client.post(self.list_url, {'name': 'Chef Special'}, format='json')
        second = self.client.post(self.list_url, {'name': 'Chef & Special'}, format='json')
        non_ascii = self.client.post(self.list_url, {'name': '\u09ac\u09bf\u09b0\u09bf\u09df\u09be\u09a8\u09bf'}, format='json')
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.data['slug'], 'chef-special-2')
        self.assertEqual(non_ascii.status_code, status.HTTP_201_CREATED)
        self.assertTrue(non_ascii.data['slug'])

    def test_renaming_retains_slug_and_read_only_fields_cannot_be_changed(self):
        self.as_manager()
        created_at = self.biryani.created_at
        response = self.client.patch(self.detail_url(self.biryani), {
            'name': 'Royal Biryani', 'slug': '', 'id': 9999, 'dishCount': 100,
            'created_at': '2000-01-01T00:00:00Z',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.biryani.refresh_from_db()
        self.assertEqual(self.biryani.slug, 'biryani')
        self.assertEqual(response.data['id'], self.biryani.pk)
        self.assertEqual(response.data['dishCount'], 1)
        self.assertEqual(self.biryani.created_at, created_at)

    def test_image_can_be_cleared_with_null_or_empty_string(self):
        self.as_manager()
        for value in (None, ''):
            with self.subTest(value=value):
                response = self.client.patch(self.detail_url(self.biryani), {'imageUrl': value}, format='json')
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data['imageUrl'], value)

    def test_anonymous_customer_and_chef_cannot_write_categories(self):
        for user in (None, self.customer, self.chef):
            self.client.force_authenticate(user=user)
            for method, url, data in (
                ('post', self.list_url, {'name': 'Forbidden'}),
                ('patch', self.detail_url(self.biryani), {'name': 'Forbidden'}),
                ('put', self.detail_url(self.biryani), {'name': 'Forbidden'}),
                ('delete', self.detail_url(self.biryani), {}),
            ):
                with self.subTest(user=user, method=method):
                    response = getattr(self.client, method)(url, data, format='json')
                    self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        self.biryani.refresh_from_db()
        self.assertEqual(self.biryani.name, 'Biryani')
        self.assertTrue(self.biryani.is_active)

    def test_custom_menu_management_grant_controls_visibility_and_writes(self):
        UserCustomPermission.objects.create(user=self.customer, granted_permissions=['menu:manage'])
        self.client.force_authenticate(user=self.customer)
        self.assertEqual(self.client.get(self.list_url).data['count'], 3)
        response = self.client.post(self.list_url, {'name': 'Authorized'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_cache_does_not_leak_inactive_categories_between_public_and_manager(self):
        for manager_first in (False, True):
            cache.clear()
            actors = (self.manager, None) if manager_first else (None, self.manager)
            for user in actors:
                self.client.force_authenticate(user=user)
                response = self.client.get(self.list_url)
                self.assertEqual(response.data['count'], 3 if user else 2)

    def test_search_slug_filter_and_ordering_have_separate_cache_entries(self):
        self.client.get(self.list_url)
        search = self.client.get(self.list_url, {'search': 'Biryani'})
        slug = self.client.get(self.list_url, {'slug': 'curries'})
        ordered = self.client.get(self.list_url, {'ordering': '-order'})
        self.assertEqual([row['id'] for row in search.data['results']], [self.biryani.pk])
        self.assertEqual([row['id'] for row in slug.data['results']], [self.curries.pk])
        self.assertEqual(ordered.data['results'][0]['id'], self.biryani.pk)

    @patch.object(PageNumberPagination, 'page_size', 1)
    def test_pagination_is_not_replaced_by_cached_first_page(self):
        first = self.client.get(self.list_url)
        second = self.client.get(self.list_url, {'page': 2})
        self.assertEqual(first.data['count'], 2)
        self.assertEqual(second.data['count'], 2)
        self.assertEqual(first.data['results'][0]['id'], self.curries.pk)
        self.assertEqual(second.data['results'][0]['id'], self.biryani.pk)

    def test_create_and_update_invalidate_public_and_manager_cache_variants(self):
        self.client.get(self.list_url)
        self.client.get(self.list_url, {'search': 'New'})
        self.as_manager()
        self.client.get(self.list_url)
        created = self.client.post(self.list_url, {'name': 'New'}, format='json')
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.client.get(self.list_url).data['count'], 4)
        self.client.patch(self.detail_url(self.biryani), {'name': 'Updated'}, format='json')
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.list_url).data['count'], 3)
        self.assertEqual(self.client.get(self.list_url, {'search': 'New'}).data['count'], 1)
        self.assertEqual(self.client.get(self.list_url, {'search': 'Updated'}).data['count'], 1)

    def test_delete_archives_and_preserves_dishes_and_can_be_reactivated(self):
        self.as_manager()
        response = self.client.delete(self.detail_url(self.biryani))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.biryani.refresh_from_db()
        self.assertFalse(self.biryani.is_active)
        self.assertTrue(Dish.objects.filter(pk=self.dish.pk).exists())
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.detail_url(self.biryani)).status_code, status.HTTP_404_NOT_FOUND)
        self.as_manager()
        restored = self.client.patch(self.detail_url(self.biryani), {'is_active': True}, format='json')
        self.assertEqual(restored.status_code, status.HTTP_200_OK)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.detail_url(self.biryani)).status_code, status.HTTP_200_OK)

    def test_archiving_category_hides_dishes_and_invalidates_popular_cache(self):
        self.assertEqual(len(self.client.get(reverse('dish-popular')).data), 1)
        self.assertEqual(len(self.client.get(reverse('dish-bestsellers')).data), 1)
        self.as_manager()
        self.client.delete(self.detail_url(self.biryani))
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(reverse('dish-list')).data['count'], 0)
        detail = self.client.get(reverse('dish-detail', kwargs={'pk': self.hidden_dish.pk}))
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(reverse('dish-popular')).data, [])
        self.assertEqual(self.client.get(reverse('dish-bestsellers')).data, [])

    def test_public_popular_cache_never_includes_inactive_category_even_when_primed_by_manager(self):
        self.as_manager()
        self.assertEqual(self.client.get(reverse('dish-list')).data['count'], 3)
        self.client.get(reverse('dish-popular'))
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse('dish-popular'))
        self.assertEqual([row['id'] for row in response.data], [self.dish.pk])

    def test_dish_changes_refresh_category_available_dish_count(self):
        self.client.get(self.list_url)
        self.as_manager()
        changed = self.client.patch(
            reverse('dish-toggle-availability', kwargs={'pk': self.dish.pk}),
            {'is_available': False}, format='json',
        )
        self.assertEqual(changed.status_code, status.HTTP_200_OK)
        self.client.force_authenticate(user=None)
        response = self.client.get(self.list_url, {'slug': self.biryani.slug})
        self.assertEqual(response.data['results'][0]['dishCount'], 0)
