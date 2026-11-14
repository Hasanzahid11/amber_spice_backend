from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from ..models import Category


def uploaded_image(image_format='PNG', size=(16, 16), padding=0):
    buffer = BytesIO()
    Image.new('RGB', size, color='orange').save(buffer, format=image_format)
    return SimpleUploadedFile(
        'client-filename.jpg', buffer.getvalue() + b'0' * padding,
        content_type=f'image/{image_format.lower()}',
    )


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'category-image-tests',
    },
})
class CategoryImageAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.manager = user_model.objects.create_user(
            username='image-manager', email='image-manager@example.com', role=user_model.Role.MANAGER,
        )
        cls.customer = user_model.objects.create_user(
            username='image-customer', email='image-customer@example.com', role=user_model.Role.CUSTOMER,
        )

    def setUp(self):
        cache.clear()
        directory = TemporaryDirectory(prefix='amber-category-upload-test-')
        self.addCleanup(directory.cleanup)
        self.media_root = Path(directory.name)
        settings = override_settings(MEDIA_ROOT=directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.addCleanup(cache.clear)
        self.client.force_authenticate(user=self.manager)
        self.url = reverse('category-list')

    def create_with_image(self, **extra):
        response = self.client.post(self.url, {
            'name': 'Seafood', 'image': uploaded_image(), **extra,
        }, format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        category = Category.objects.get(pk=response.data['id'])
        return category, response

    def detail_url(self, category):
        return reverse('category-detail', kwargs={'pk': category.pk})

    def test_multipart_create_stores_real_file_and_returns_public_url_on_subsequent_reads(self):
        category, response = self.create_with_image(order='3', is_active='true')
        self.assertIsNone(category.image_url)
        self.assertEqual(category.order, 3)
        self.assertRegex(category.image.name, r'^menu/categories/[a-f0-9]{32}\.png$')
        self.assertTrue(category.image.storage.exists(category.image.name))
        with category.image.open('rb') as stored:
            self.assertEqual(Image.open(stored).format, 'PNG')
        url = response.data['imageUrl']
        self.assertEqual(url, f'http://testserver/media/{category.image.name}')
        self.assertNotIn('image', response.data)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.detail_url(category)).data['imageUrl'], url)
        self.assertEqual(self.client.get(self.url).data['results'][0]['imageUrl'], url)

    def test_supported_formats_use_actual_content_extension_and_multipart_false_is_preserved(self):
        for image_format, extension in [('JPEG', 'jpg'), ('PNG', 'png'), ('WEBP', 'webp')]:
            with self.subTest(image_format=image_format):
                category, response = self.create_with_image(
                    name=image_format, image=uploaded_image(image_format), is_active='false',
                )
                self.assertTrue(category.image.name.endswith(f'.{extension}'))
                self.assertFalse(response.data['is_active'])

    def test_corrupt_unsupported_oversized_and_excessive_dimension_images_are_rejected(self):
        invalid_files = [
            SimpleUploadedFile('fake.png', b'not a real image', content_type='image/png'),
            uploaded_image('GIF'),
            uploaded_image(padding=5 * 1024 * 1024),
            uploaded_image(size=(6001, 1)),
        ]
        for image in invalid_files:
            with self.subTest(size=image.size):
                response = self.client.post(self.url, {'name': 'Invalid', 'image': image}, format='multipart')
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn('image', response.data)
        self.assertFalse(Category.objects.exists())
        self.assertEqual(list(self.media_root.rglob('*')), [])

    def test_duplicate_name_and_conflicting_url_do_not_leave_uploaded_files(self):
        Category.objects.create(name='Seafood')
        for payload, field in [
            ({'name': 'seafood'}, 'name'),
            ({'name': 'Other', 'imageUrl': 'https://example.com/other.png'}, 'image'),
        ]:
            response = self.client.post(self.url, {**payload, 'image': uploaded_image()}, format='multipart')
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn(field, response.data)
        self.assertEqual(list(self.media_root.rglob('*')), [])

    def test_anonymous_and_customer_cannot_upload(self):
        for user in [None, self.customer]:
            self.client.force_authenticate(user=user)
            response = self.client.post(self.url, {'name': 'Denied', 'image': uploaded_image()}, format='multipart')
            self.assertIn(response.status_code, (401, 403))
        self.assertFalse(Category.objects.exists())
        self.assertEqual(list(self.media_root.rglob('*')), [])

    def test_replacing_file_deletes_previous_image_after_commit_and_invalidates_list(self):
        category, first = self.create_with_image()
        old_name = category.image.name
        self.client.get(self.url)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(self.detail_url(category), {'image': uploaded_image('WEBP')}, format='multipart')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertTrue(category.image.storage.exists(old_name))
        category.refresh_from_db()
        self.assertFalse(category.image.storage.exists(old_name))
        self.assertTrue(category.image.storage.exists(category.image.name))
        self.assertNotEqual(first.data['imageUrl'], response.data['imageUrl'])
        self.assertEqual(self.client.get(self.url).data['results'][0]['imageUrl'], response.data['imageUrl'])

    def test_json_null_clears_uploaded_image_and_deletes_file_after_commit(self):
        category, _ = self.create_with_image()
        old_name, storage = category.image.name, category.image.storage
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(self.detail_url(category), {'image': None}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data['imageUrl'])
        category.refresh_from_db()
        self.assertFalse(category.image)
        self.assertFalse(storage.exists(old_name))

    def test_external_url_replaces_upload_without_changing_response_contract(self):
        category, _ = self.create_with_image()
        old_name, storage = category.image.name, category.image.storage
        url = 'https://example.com/seafood.webp'
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(self.detail_url(category), {'imageUrl': url}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['imageUrl'], url)
        category.refresh_from_db()
        self.assertFalse(category.image)
        self.assertEqual(category.image_url, url)
        self.assertFalse(storage.exists(old_name))

    def test_archiving_preserves_image_for_restoration(self):
        category, first = self.create_with_image()
        self.assertEqual(self.client.delete(self.detail_url(category)).status_code, 204)
        category.refresh_from_db()
        self.assertFalse(category.is_active)
        self.assertTrue(category.image.storage.exists(category.image.name))
        restored = self.client.patch(self.detail_url(category), {'is_active': True}, format='json')
        self.assertEqual(restored.status_code, 200, restored.data)
        self.assertEqual(restored.data['imageUrl'], first.data['imageUrl'])
