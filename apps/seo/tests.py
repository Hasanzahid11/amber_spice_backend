from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.menu.models import Category, Dish
from .models import RestaurantSEOProfile, PageSEOMetadata, MarketingCampaign, OptimizedImageMetadata

User = get_user_model()


class SEOMarketingTests(APITestCase):
    """
    Test suite for SEO & Marketing app:
    Schema.org/Restaurant & Menu JSON-LD, XML Sitemap, robots.txt,
    Local SEO & Google Maps integration, OpenGraph tags, and UTM campaign tracking.
    """

    def setUp(self):
        # Admin User
        self.admin = User.objects.create_user(
            username='admin_seo',
            email='admin@amberspice.ie',
            password='Password123!',
            role=User.Role.OWNER_ADMIN
        )

        # Profile
        self.profile = RestaurantSEOProfile.get_profile()
        self.profile.restaurant_name = 'Amber Spice Dublin'
        self.profile.canonical_domain = 'https://amberspice.ie'
        self.profile.street_address = '12 Merrion Row'
        self.profile.city = 'Dublin'
        self.profile.postal_code = 'D02 X224'
        self.profile.phone = '+35312345678'
        self.profile.save()

        # Category and Dish for dynamic sitemap and menu schema
        self.category = Category.objects.create(name='Traditional Curries', slug='traditional-curries')
        self.dish = Dish.objects.create(
            category=self.category,
            name='Chicken Tikka Masala',
            slug='chicken-tikka-masala',
            price=Decimal('16.50'),
            description='Slow-cooked in creamy tomato gravy with aromatic fenugreek.'
        )

        # Page SEO metadata
        self.home_page = PageSEOMetadata.objects.create(
            page_identifier='home',
            page_path='/',
            meta_title='Amber Spice | Best Indian Restaurant Dublin',
            meta_description='Award-winning authentic Indian cuisine in the heart of Dublin.',
            canonical_url='https://amberspice.ie/',
            sitemap_priority=Decimal('1.0')
        )

        self.menu_page = PageSEOMetadata.objects.create(
            page_identifier='menu',
            page_path='/menu',
            meta_title='A La Carte Menu | Amber Spice Dublin',
            meta_description='Browse our full dinner and lunch menu with tandoori and curries.',
            sitemap_priority=Decimal('0.9')
        )

    def test_restaurant_schema_jsonld(self):
        """
        Tests GET /api/v1/seo/schema/restaurant/
        Validates Schema.org/Restaurant format for Google Rich Snippets.
        """
        res = self.client.get('/api/v1/seo/schema/restaurant/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        schema = res.data

        self.assertEqual(schema['@context'], 'https://schema.org')
        self.assertEqual(schema['@type'], 'Restaurant')
        self.assertEqual(schema['name'], 'Amber Spice Dublin')
        self.assertEqual(schema['telephone'], '+35312345678')
        self.assertIn('address', schema)
        self.assertEqual(schema['address']['addressLocality'], 'Dublin')
        self.assertIn('geo', schema)
        self.assertIn('openingHoursSpecification', schema)
        self.assertIn('potentialAction', schema)

    def test_menu_schema_jsonld(self):
        """
        Tests GET /api/v1/seo/schema/menu/
        Validates Schema.org/Menu with MenuSection and MenuItem.
        """
        res = self.client.get('/api/v1/seo/schema/menu/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        schema = res.data

        self.assertEqual(schema['@context'], 'https://schema.org')
        self.assertEqual(schema['@type'], 'Menu')
        self.assertIn('hasMenuSection', schema)
        self.assertTrue(len(schema['hasMenuSection']) > 0)

        section = schema['hasMenuSection'][0]
        self.assertEqual(section['name'], 'Traditional Curries')
        self.assertTrue(len(section['hasMenuItem']) > 0)
        item = section['hasMenuItem'][0]
        self.assertEqual(item['name'], 'Chicken Tikka Masala')
        self.assertEqual(item['offers']['price'], '16.50')
        self.assertEqual(item['offers']['priceCurrency'], 'EUR')

    def test_sitemap_xml_generation(self):
        """
        Tests GET /api/v1/seo/sitemap.xml
        Validates XML header, core URLs, category clean URLs, and dish clean URLs.
        """
        res = self.client.get('/api/v1/seo/sitemap.xml')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('application/xml', res['Content-Type'])
        xml = res.content.decode('utf-8')

        self.assertIn('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">', xml)
        self.assertIn('https://amberspice.ie/', xml)
        self.assertIn('https://amberspice.ie/menu', xml)
        self.assertIn('https://amberspice.ie/menu/traditional-curries', xml)
        self.assertIn('https://amberspice.ie/menu/traditional-curries/chicken-tikka-masala', xml)
        self.assertIn('<priority>1.0</priority>', xml)

    def test_robots_txt_generation(self):
        """
        Tests GET /api/v1/seo/robots.txt
        Validates search crawler directives and sitemap URL link.
        """
        res = self.client.get('/api/v1/seo/robots.txt')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('text/plain', res['Content-Type'])
        content = res.content.decode('utf-8')

        self.assertIn('User-agent: *', content)
        self.assertIn('Allow: /', content)
        self.assertIn('Disallow: /admin/', content)
        self.assertIn('Sitemap: https://amberspice.ie/sitemap.xml', content)

    def test_local_seo_and_google_maps_bundle(self):
        """
        Tests GET /api/v1/seo/local/
        Validates NAP, GeoCoordinates, Google Maps links, and directions URL.
        """
        res = self.client.get('/api/v1/seo/local/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data

        self.assertEqual(data['restaurantName'], 'Amber Spice Dublin')
        self.assertEqual(data['nap']['city'], 'Dublin')
        self.assertEqual(data['nap']['postalCode'], 'D02 X224')
        self.assertIn('geo', data)
        self.assertIn('googleMaps', data)
        self.assertIn('directionsUrl', data['googleMaps'])
        self.assertIn('schemaJsonLd', data)

    def test_page_metadata_ssr_hydration_endpoint(self):
        """
        Tests GET /api/v1/seo/metadata/?path=/menu
        Validates OpenGraph, Twitter card, canonical URL, and Cache-Control header.
        """
        res = self.client.get('/api/v1/seo/metadata/?path=/menu')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('public, max-age', res['Cache-Control'])

        data = res.data
        self.assertEqual(data['metaTitle'], 'A La Carte Menu | Amber Spice Dublin')
        self.assertIn('openGraph', data)
        self.assertEqual(data['openGraph']['title'], 'A La Carte Menu | Amber Spice Dublin')
        self.assertIn('twitter', data)
        self.assertEqual(data['twitter']['card'], 'summary_large_image')
        self.assertIn('schemaJsonLd', data)

    def test_marketing_campaign_utm_tracking(self):
        """
        Tests MarketingCampaign UTM generation and click tracking.
        """
        camp = MarketingCampaign.objects.create(
            name='Google Local Search Dublin',
            utm_source='google',
            utm_medium='cpc',
            utm_campaign='dublin_takeaway_lunch',
            target_path='/order'
        )
        self.assertIn('utm_source=google', camp.tracking_url)
        self.assertIn('utm_campaign=dublin_takeaway_lunch', camp.tracking_url)

        # Track Click
        res_click = self.client.post(f'/api/v1/seo/campaigns/{camp.id}/track-click/')
        self.assertEqual(res_click.status_code, status.HTTP_200_OK)
        camp.refresh_from_db()
        self.assertEqual(camp.clicks_count, 1)

        # Track Conversion
        res_conv = self.client.post(f'/api/v1/seo/campaigns/{camp.id}/track-conversion/')
        self.assertEqual(res_conv.status_code, status.HTTP_200_OK)
        camp.refresh_from_db()
        self.assertEqual(camp.conversions_count, 1)

