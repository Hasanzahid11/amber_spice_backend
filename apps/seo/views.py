from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsManagerOrAdmin
from .models import RestaurantSEOProfile, PageSEOMetadata, MarketingCampaign, OptimizedImageMetadata
from .serializers import (
    RestaurantSEOProfileSerializer,
    PageSEOMetadataSerializer,
    MarketingCampaignSerializer,
    OptimizedImageMetadataSerializer,
    PageSEOBundleResponseSerializer,
    LocalSEOBundleResponseSerializer,
)
from .services import (
    get_restaurant_schema_jsonld,
    get_menu_schema_jsonld,
    generate_sitemap_xml,
    generate_robots_txt,
    get_local_seo_bundle,
    get_page_seo_bundle,
)


class PageSEODataView(APIView):
    """
    GET /api/v1/seo/metadata/
    Public API used by website frontend (Next.js, React, Nuxt) for Server-Side Rendering (SSR)
    and dynamic metadata hydration.
    Query params:
    - path: e.g. '/', '/menu', '/reservations', '/order', '/contact'
    - page: e.g. 'home', 'menu', 'reservations'
    Returns: metaTitle, metaDescription, canonicalUrl, OpenGraph, Twitter Card, and Schema.org JSON-LD.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        path = request.query_params.get('path') or request.query_params.get('page') or 'home'
        bundle = get_page_seo_bundle(path)
        serializer = PageSEOBundleResponseSerializer(bundle)
        response = Response(serializer.data)
        # Fast page loading caching header (public, max-age 15 mins)
        response['Cache-Control'] = 'public, max-age=900, stale-while-revalidate=60'
        return response


class LocalSEODataView(APIView):
    """
    GET /api/v1/seo/local/
    Public API providing Google Business Profile, Google Maps embed, GeoCoordinates,
    NAP (Name, Address, Phone), and opening hours.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        bundle = get_local_seo_bundle()
        serializer = LocalSEOBundleResponseSerializer(bundle)
        response = Response(serializer.data)
        response['Cache-Control'] = 'public, max-age=1800'
        return response


class RestaurantSchemaView(APIView):
    """
    GET /api/v1/seo/schema/restaurant/
    Returns Schema.org/Restaurant JSON-LD matching Google Rich Snippet guidelines.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        schema = get_restaurant_schema_jsonld()
        return Response(schema)


class MenuSchemaView(APIView):
    """
    GET /api/v1/seo/schema/menu/
    Returns Schema.org/Menu with MenuSection and MenuItem objects.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        schema = get_menu_schema_jsonld()
        return Response(schema)


class SitemapXMLView(APIView):
    """
    GET /sitemap.xml or /api/v1/seo/sitemap.xml
    Dynamically generates standard XML Sitemap for Google Search Console and crawlers.
    Indexes core site pages, category clean URLs, and dish clean URLs.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        domain = request.build_absolute_uri('/')
        xml_content = generate_sitemap_xml(domain_override=domain)
        response = HttpResponse(xml_content, content_type='application/xml; charset=utf-8')
        response['Cache-Control'] = 'public, max-age=3600'
        return response


class RobotsTxtView(APIView):
    """
    GET /robots.txt or /api/v1/seo/robots.txt
    Directs search engines to crawl public pages and discover sitemap.xml.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        domain = request.build_absolute_uri('/')
        robots_content = generate_robots_txt(domain_override=domain)
        response = HttpResponse(robots_content, content_type='text/plain; charset=utf-8')
        response['Cache-Control'] = 'public, max-age=86400'
        return response


class RestaurantSEOProfileView(APIView):
    """
    GET /api/v1/seo/profile/
    PUT/PATCH /api/v1/seo/profile/
    Admin management of global restaurant SEO, Google Business info, and marketing pixels.
    """
    permission_classes = [IsManagerOrAdmin]

    def get(self, request):
        profile = RestaurantSEOProfile.get_profile()
        serializer = RestaurantSEOProfileSerializer(profile)
        return Response(serializer.data)

    def put(self, request):
        profile = RestaurantSEOProfile.get_profile()
        serializer = RestaurantSEOProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            'message': 'Restaurant SEO Profile updated successfully.',
            'profile': serializer.data
        })

    def patch(self, request):
        return self.put(request)


class PageSEOMetadataViewSet(viewsets.ModelViewSet):
    """
    Admin CRUD for Page SEO Metadata (meta tags, OG tags, canonical URLs).
    """
    queryset = PageSEOMetadata.objects.all()
    serializer_class = PageSEOMetadataSerializer
    permission_classes = [IsManagerOrAdmin]


class MarketingCampaignViewSet(viewsets.ModelViewSet):
    """
    Admin CRUD for Marketing & UTM Campaigns.
    Includes tracking endpoints for click and conversion attribution.
    """
    queryset = MarketingCampaign.objects.all()
    serializer_class = MarketingCampaignSerializer
    permission_classes = [IsManagerOrAdmin]

    @action(detail=True, methods=['post'], permission_classes=[permissions.AllowAny], url_path='track-click')
    def track_click(self, request, pk=None):
        camp = self.get_object()
        camp.clicks_count += 1
        camp.save(update_fields=['clicks_count', 'updated_at'])
        return Response({'message': 'Click tracked.', 'clicks': camp.clicks_count})

    @action(detail=True, methods=['post'], permission_classes=[permissions.AllowAny], url_path='track-conversion')
    def track_conversion(self, request, pk=None):
        camp = self.get_object()
        camp.conversions_count += 1
        camp.save(update_fields=['conversions_count', 'updated_at'])
        return Response({'message': 'Conversion tracked.', 'conversions': camp.conversions_count})


class OptimizedImageViewSet(viewsets.ModelViewSet):
    """
    Admin management for Image SEO metadata (alt text, WebP URLs, lazy-load flags).
    """
    queryset = OptimizedImageMetadata.objects.all()
    serializer_class = OptimizedImageMetadataSerializer
    permission_classes = [IsManagerOrAdmin]

