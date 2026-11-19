from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.engagement.models import RestaurantProfile
from apps.menu.models import Category, Dish
from .models import SEOMetadata, RedirectRule
from .services import ensure_default_metadata, build_restaurant_schema, generate_sitemap_xml, generate_robots_txt, audit_seo

User = get_user_model()


class SEOTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            username='seoadmin',
            email='admin@amberspice.com',
            password='TestPassword123!',
            role=User.Role.SUPER_ADMIN,
        )
        self.profile = RestaurantProfile.objects.create(
            name='Amber Spice Dublin',
            phone='+353 1 234 5678',
            address='14 South William Street',
            city='Dublin',
            latitude=Decimal('53.3421000'),
            longitude=Decimal('-6.2625000'),
            opening_hours='Mon-Sun 17:00-22:00',
        )
        self.category = Category.objects.create(
            name='Royal Biryanis',
            slug='royal-biryanis',
            order=1,
            is_active=True,
        )
        self.dish = Dish.objects.create(
            name='Awadhi Chicken Biryani',
            category=self.category,
            price=Decimal('18.50'),
            is_available=True,
        )

    def test_default_metadata_seeding(self):
        ensure_default_metadata()
        count = SEOMetadata.objects.count()
        self.assertGreaterEqual(count, 8)
        home = SEOMetadata.objects.get(path='/')
        self.assertIn('Amber Spice', home.title)
        self.assertIn('Dublin', home.description)

    def test_seo_resolve_endpoint(self):
        response = self.client.get('/api/v1/seo/metadata/resolve/?path=/menu')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['path'], '/menu')
        self.assertIn('Menu', data['title'])
        self.assertIn('openGraph', data)
        self.assertIn('twitter', data)
        self.assertIn('structuredData', data)
        self.assertEqual(data['structuredData']['@type'], 'Restaurant')

    def test_seo_resolve_fallback(self):
        response = self.client.get('/api/v1/seo/metadata/resolve/?path=/non-existent-page')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('Amber Spice', data['title'])

    def test_dynamic_sitemap(self):
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/xml', response['Content-Type'])
        content = response.content.decode('utf-8')
        self.assertIn('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">', content)
        self.assertIn('royal-biryanis', content)
        self.assertIn(f'dish={self.dish.id}', content)

    def test_dynamic_robots(self):
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/plain', response['Content-Type'])
        content = response.content.decode('utf-8')
        self.assertIn('User-agent: *', content)
        self.assertIn('Disallow: /admin/', content)
        self.assertIn('Sitemap:', content)

    def test_restaurant_schema_endpoint(self):
        response = self.client.get('/api/v1/seo/schema/restaurant/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['@context'], 'https://schema.org')
        self.assertEqual(data['@type'], 'Restaurant')
        self.assertEqual(data['name'], 'Amber Spice Dublin')
        self.assertEqual(data['telephone'], '+353 1 234 5678')

    def test_seo_audit_unauthorized(self):
        response = self.client.get('/api/v1/seo/audit/')
        self.assertEqual(response.status_code, 401)

    def test_seo_audit_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/v1/seo/audit/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('overall_score', data)
        self.assertGreaterEqual(data['overall_score'], 80)
        self.assertIn('reports', data)
