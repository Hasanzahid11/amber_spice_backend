from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from ..models import Category, Dish
from .test_category_images import uploaded_image


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'dish-create-tests'}})
class DishAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.manager = user_model.objects.create_user(username='dish-manager', email='dish-manager@example.com', first_name='Menu', last_name='Owner', role=user_model.Role.MANAGER)
        cls.editor = user_model.objects.create_user(username='dish-editor', email='dish-editor@example.com', role=user_model.Role.MANAGER)
        cls.customer = user_model.objects.create_user(username='dish-customer', email='dish-customer@example.com')
        cls.chef = user_model.objects.create_user(username='dish-chef', email='dish-chef@example.com', role=user_model.Role.CHEF)
        cls.category = Category.objects.create(name='Main Courses', created_by=cls.manager)
        cls.hidden = Category.objects.create(name='Hidden', is_active=False)

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.client.force_authenticate(self.manager)
        directory = TemporaryDirectory(prefix='amber-dish-test-')
        self.addCleanup(directory.cleanup)
        self.media_root = Path(directory.name)
        settings = override_settings(MEDIA_ROOT=directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.url = reverse('dish-list')

    def create(self, **extra):
        response = self.client.post(self.url, {'name': 'Fresh Dish', 'category': self.category.pk, 'price': '12.50', **extra}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return Dish.objects.get(pk=response.data['id']), response

    def detail(self, dish):
        return reverse('dish-detail', kwargs={'pk': dish.pk})

    def test_create_and_edit_survive_reads_and_creator_cannot_be_forged_or_reassigned(self):
        dish, response = self.create(created_by=self.editor.pk, addedBy={'id': self.editor.pk}, rating=5, ordersCount=999)
        self.assertEqual(dish.created_by, self.manager)
        self.assertEqual(response.data['addedBy'], {'id': self.manager.pk, 'name': 'Menu Owner', 'role': 'manager'})
        self.assertEqual(response.data['category'], self.category.pk)
        self.assertEqual(response.data['rating'], 0)
        self.assertEqual(response.data['ordersCount'], 0)
        self.client.force_authenticate(self.editor)
        updated = self.client.patch(self.detail(dish), {'name': 'Renamed Dish', 'price': '14.25', 'created_by': self.editor.pk, 'addedBy': None}, format='json')
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data['addedBy']['id'], self.manager.pk)
        self.assertEqual(updated.data['slug'], 'fresh-dish')
        self.client.force_authenticate(None)
        public = self.client.get(self.url, {'category': self.category.pk})
        self.assertEqual(public.data['results'][0]['name'], 'Renamed Dish')
        self.assertEqual(public.data['results'][0]['price'], '14.25')
        self.assertIsNone(public.data['results'][0]['addedBy'])
        self.assertEqual(self.client.get(reverse('category-list')).data['results'][0]['dishCount'], 1)

    def test_category_creator_is_server_assigned_and_remains_on_edit(self):
        response = self.client.post(reverse('category-list'), {'name': 'New Category', 'created_by': self.editor.pk}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        category = Category.objects.get(pk=response.data['id'])
        self.assertEqual(category.created_by, self.manager)
        self.client.force_authenticate(self.editor)
        response = self.client.patch(reverse('category-detail', kwargs={'pk': category.pk}), {'description': 'Updated', 'created_by': self.editor.pk}, format='json')
        self.assertEqual(response.data['addedBy']['id'], self.manager.pk)
        self.client.force_authenticate(None)
        response = self.client.get(reverse('category-detail', kwargs={'pk': category.pk}))
        self.assertIsNone(response.data['addedBy'])

    def test_existing_records_do_not_get_a_fabricated_creator(self):
        response = self.client.get(reverse('category-detail', kwargs={'pk': self.hidden.pk}))
        self.assertIsNone(response.data['addedBy'])

    def test_invalid_category_prices_spice_station_and_dietary_are_rejected(self):
        for changes, field in [
            ({'category': self.hidden.pk}, 'category'), ({'category': 99999}, 'category'),
            ({'price': '-1'}, 'price'), ({'price': '0'}, 'price'), ({'price': '2.345'}, 'price'),
            ({'name': ''}, 'name'), ({'spicyLevel': 4}, 'spicyLevel'), ({'spicyLevel': -1}, 'spicyLevel'),
            ({'station': 'unknown'}, 'station'), ({'dietary': ['unknown']}, 'dietary'),
            ({'imageUrl': 'ftp://example.com/food.png'}, 'imageUrl'),
        ]:
            with self.subTest(changes=changes):
                response = self.client.post(self.url, {'name': 'Invalid', 'category': self.category.pk, 'price': '5', **changes}, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn(field, response.data)
        self.assertFalse(Dish.objects.exists())

    def test_slug_generation_handles_collisions_and_non_ascii_names(self):
        first, _ = self.create(name='Chef Special')
        second, _ = self.create(name='Chef & Special')
        other, _ = self.create(name='\u09ac\u09bf\u09b0\u09bf\u09df\u09be\u09a8\u09bf')
        self.assertEqual(first.slug, 'chef-special')
        self.assertEqual(second.slug, 'chef-special-2')
        self.assertTrue(other.slug)

    def test_multipart_image_upload_and_edit_preserve_or_replace_real_file(self):
        response = self.client.post(self.url, {'name': 'Uploaded Dish', 'category': self.category.pk, 'price': '15.50', 'image': uploaded_image(), 'dietary': '["halal"]', 'isAvailable': 'false'}, format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        dish = Dish.objects.get(pk=response.data['id'])
        old_name = dish.image.name
        self.assertRegex(old_name, r'^menu/dishes/[a-f0-9]{32}\.png$')
        self.assertEqual(response.data['dietary'], ['halal'])
        self.assertFalse(response.data['isAvailable'])
        self.assertNotIn('image', response.data)
        updated = self.client.patch(self.detail(dish), {'price': '16.00'}, format='json')
        self.assertEqual(updated.data['imageUrl'], response.data['imageUrl'])
        with self.captureOnCommitCallbacks(execute=True):
            updated = self.client.patch(self.detail(dish), {'image': uploaded_image('WEBP'), 'dietary': '[]'}, format='multipart')
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data['dietary'], [])
        self.assertFalse(dish.image.storage.exists(old_name))
        dish.refresh_from_db()
        self.assertTrue(dish.image.storage.exists(dish.image.name))
        with self.captureOnCommitCallbacks(execute=True):
            cleared = self.client.patch(self.detail(dish), {'image': None}, format='json')
        self.assertEqual(cleared.status_code, 200, cleared.data)
        self.assertEqual(cleared.data['imageUrl'], '')
        self.assertFalse(dish.image.storage.exists(dish.image.name))

    def test_bad_upload_is_rejected_without_a_file_or_dish(self):
        for image in [uploaded_image('GIF'), uploaded_image(padding=5 * 1024 * 1024)]:
            response = self.client.post(self.url, {'name': 'Bad', 'category': self.category.pk, 'price': '4', 'image': image}, format='multipart')
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn('image', response.data)
        self.assertFalse(Dish.objects.exists())
        self.assertEqual(list(self.media_root.rglob('*')), [])

    def test_multipart_also_accepts_standard_repeated_dietary_values(self):
        response = self.client.post(self.url, {'name': 'Dietary Dish', 'category': self.category.pk, 'price': '4', 'dietary': ['halal', 'dairy-free']}, format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['dietary'], ['halal', 'dairy-free'])

    def test_popular_and_category_cache_do_not_leak_creator_between_audiences(self):
        self.create(isPopular=True)
        for manager_first in [True, False]:
            cache.clear()
            for user in ([self.manager, None] if manager_first else [None, self.manager]):
                self.client.force_authenticate(user)
                for url, is_page in [(reverse('dish-popular'), False), (reverse('category-list'), True)]:
                    response = self.client.get(url)
                    rows = response.data['results'] if is_page else response.data
                    self.assertTrue(rows)
                    row = next(row for row in rows if row['id'] == self.category.pk) if is_page else rows[0]
                    self.assertEqual(row['addedBy'] is not None, user is not None)

    def test_unauthorized_users_cannot_create_but_chef_can_toggle_with_validation(self):
        dish, _ = self.create()
        for user in [None, self.customer, self.chef]:
            self.client.force_authenticate(user)
            response = self.client.post(self.url, {'name': 'Denied', 'category': self.category.pk, 'price': '3'}, format='json')
            self.assertIn(response.status_code, [401, 403])
        url = reverse('dish-toggle-availability', kwargs={'pk': dish.pk})
        self.assertEqual(self.client.patch(url, {'is_available': 'garbage'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(url, {'is_available': False}, format='json').status_code, 200)
        dish.refresh_from_db()
        self.assertFalse(dish.is_available)
        self.assertEqual(dish.created_by, self.manager)

    def test_django_admin_also_assigns_creator_on_create(self):
        request = RequestFactory().get('/admin/')
        request.user = self.manager
        category = Category(name='Django Admin Category')
        admin.site._registry[Category].save_model(request, category, None, False)
        self.assertEqual(category.created_by, self.manager)
        dish = Dish(name='Django Admin Dish', category=category, price='9')
        admin.site._registry[Dish].save_model(request, dish, None, False)
        self.assertEqual(dish.created_by, self.manager)
