from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from apps.accounts.models import RolePermissionConfig
from .models import BannerSlide

User = get_user_model()


class BannerSlideTests(APITestCase):
    def setUp(self):
        # Configure manager role permissions
        RolePermissionConfig.objects.create(
            role='manager',
            permissions=['settings:manage', 'menu:view', 'orders:view']
        )
        self.admin_user = User.objects.create_user(
            username='admin_hero',
            email='admin_hero@example.com',
            password='password123',
            role='manager'
        )
        self.customer = User.objects.create_user(
            username='customer_hero',
            email='customer_hero@example.com',
            password='password123',
            role='customer'
        )

    def test_public_can_get_banners_and_defaults_seeded(self):
        response = self.client.get('/api/v1/content/banners/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify 4 default slides seeded
        self.assertEqual(BannerSlide.objects.count(), 4)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 4)
        first_slide = results[0]
        self.assertEqual(first_slide['tag'], 'SPECIAL WEEKEND FEAST')
        self.assertEqual(first_slide['titleLine1'], 'Celebrate with Gourmet')
        self.assertEqual(first_slide['titleLine2'], 'Family Combos')
        self.assertEqual(first_slide['ctaText'], 'Book a Table')
        self.assertEqual(first_slide['ctaLink'], 'reservation')
        self.assertTrue(first_slide['isActive'])

    def test_inactive_banner_is_hidden_from_public(self):
        # Seed banners
        self.client.get('/api/v1/content/banners/')
        first = BannerSlide.objects.first()
        first.is_active = False
        first.save()

        response = self.client.get('/api/v1/content/banners/')
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 3)
        tags = [r['tag'] for r in results]
        self.assertNotIn(first.tag, tags)

    def test_unauthenticated_cannot_create_or_modify_banners(self):
        create_payload = {
            'tag': 'NEW LAUNCH',
            'titleLine1': 'Brand New',
            'titleLine2': 'Chef Platters',
            'subtitle': 'Try our latest arrivals.',
            'ctaText': 'Explore',
            'ctaLink': 'menu',
            'imageUrl': '/figma-assets/grill.png',
            'displayOrder': 5,
            'isActive': True,
        }
        res_create = self.client.post('/api/v1/content/banners/', create_payload, format='json')
        self.assertEqual(res_create.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_create_update_and_delete_banner(self):
        self.client.force_authenticate(user=self.admin_user)
        # Create
        create_payload = {
            'tag': 'FESTIVAL SPECIAL',
            'titleLine1': 'Mughlai Rogan Josh',
            'titleLine2': 'Delight Bowl',
            'subtitle': 'Slow cooked lamb shanks.',
            'ctaText': 'Order Now',
            'ctaLink': 'menu',
            'imageUrl': '/figma-assets/curry.png',
            'displayOrder': 10,
            'isActive': True,
        }
        create_res = self.client.post('/api/v1/content/banners/', create_payload, format='json')
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        new_id = create_res.data['id']

        # Update
        update_payload = {
            'tag': 'FESTIVAL SPECIAL UPDATED',
            'titleLine1': 'Mughlai Rogan Josh Royal',
            'titleLine2': 'Super Bowl',
            'ctaText': 'Book Now',
            'ctaLink': 'reservation',
            'imageUrl': '/figma-assets/curry.png',
            'displayOrder': 1,
            'isActive': True,
        }
        update_res = self.client.put(f'/api/v1/content/banners/{new_id}/', update_payload, format='json')
        self.assertEqual(update_res.status_code, status.HTTP_200_OK)
        self.assertEqual(update_res.data['tag'], 'FESTIVAL SPECIAL UPDATED')
        self.assertEqual(update_res.data['titleLine1'], 'Mughlai Rogan Josh Royal')
        self.assertEqual(update_res.data['ctaText'], 'Book Now')
        self.assertEqual(update_res.data['ctaLink'], 'reservation')

        # Delete
        delete_res = self.client.delete(f'/api/v1/content/banners/{new_id}/')
        self.assertEqual(delete_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(BannerSlide.objects.filter(id=new_id).exists())


class ContactMessageTests(APITestCase):
    def setUp(self):
        RolePermissionConfig.objects.create(
            role='manager',
            permissions=['customers:view', 'settings:manage']
        )
        self.admin = User.objects.create_user(
            username='admin_contact',
            email='admin_contact@example.com',
            password='password123',
            role='admin',
            is_staff=True,
        )
        self.customer = User.objects.create_user(
            username='customer_contact',
            email='customer_contact@example.com',
            password='password123',
            role='customer',
        )

    def test_public_can_submit_contact_message_and_notification_created(self):
        from apps.notifications.models import Notification
        from .models import ContactMessage
        payload = {
            'fullName': 'Siobhan Kelly',
            'email': 'siobhan@example.ie',
            'subject': 'Private Dining Inquiry',
            'message': 'We would like to book a private event for 25 people next Friday.',
        }
        res = self.client.post('/api/v1/contact/messages/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['fullName'], 'Siobhan Kelly')
        self.assertEqual(res.data['status'], 'new')

        # Verify DB record
        msg = ContactMessage.objects.filter(email='siobhan@example.ie').first()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.full_name, 'Siobhan Kelly')

        # Verify operational Notification created for admin
        notif = Notification.objects.filter(type='contact_message').first()
        self.assertIsNotNone(notif)
        self.assertIn('Private Dining Inquiry', notif.title)
        self.assertIn('Siobhan Kelly', notif.message)
        self.assertEqual(notif.data['email'], 'siobhan@example.ie')

    def test_staff_can_list_and_update_contact_message_status(self):
        from .models import ContactMessage
        msg = ContactMessage.objects.create(
            full_name='Liam Neeson',
            email='liam@example.ie',
            subject='Table question',
            message='Is outdoor patio open?',
            status='new',
        )

        # Unauthenticated cannot list
        res_anon = self.client.get('/api/v1/contact/messages/')
        self.assertEqual(res_anon.status_code, status.HTTP_401_UNAUTHORIZED)

        # Admin can list
        self.client.force_authenticate(user=self.admin)
        res_admin = self.client.get('/api/v1/contact/messages/')
        self.assertEqual(res_admin.status_code, status.HTTP_200_OK)
        results = res_admin.data.get('results', res_admin.data)
        self.assertTrue(any(m['email'] == 'liam@example.ie' for m in results))

        # Admin can update status to read then resolved
        patch_res = self.client.patch(f'/api/v1/contact/messages/{msg.id}/', {'status': 'resolved'}, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data['status'], 'resolved')
        msg.refresh_from_db()
        self.assertEqual(msg.status, 'resolved')
