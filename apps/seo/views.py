from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SEOMetadata, RedirectRule
from .serializers import (
    SEOMetadataSerializer,
    SEOResolveSerializer,
    RedirectRuleSerializer,
    SEOAuditReportSerializer,
)
from .services import (
    build_restaurant_schema,
    generate_sitemap_xml,
    generate_robots_txt,
    audit_seo,
    ensure_default_metadata,
)


class SEOMetadataViewSet(viewsets.ModelViewSet):
    queryset = SEOMetadata.objects.all()
    serializer_class = SEOMetadataSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'resolve']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def list(self, request, *args, **kwargs):
        ensure_default_metadata()
        return super().list(request, *args, **kwargs)

    @extend_schema(
        parameters=[OpenApiParameter('path', str, description="Relative URL path, e.g. '/', '/menu', '/offers'")],
        responses=SEOResolveSerializer,
        description="Public endpoint to resolve exact SEO metadata, OpenGraph, Twitter, and Schema.org for any route."
    )
    @action(detail=False, methods=['get'])
    def resolve(self, request):
        ensure_default_metadata()
        raw_path = request.query_params.get('path', '/').strip()
        path = raw_path if raw_path.startswith('/') else f"/{raw_path}"
        if path != '/' and path.endswith('/'):
            path = path[:-1]

        meta = SEOMetadata.objects.filter(path=path, is_active=True).first()
        if not meta:
            meta = SEOMetadata.objects.filter(path='/', is_active=True).first()

        restaurant_schema = build_restaurant_schema()
        merged_schema = meta.structured_data if meta and meta.structured_data else restaurant_schema

        data = {
            'path': meta.path if meta else path,
            'title': meta.title if meta else 'Amber Spice | Authentic Indian Cuisine Dublin',
            'description': meta.description if meta else 'Authentic Awadhi & Old Delhi flavors in Dublin.',
            'keywords': meta.keywords if meta else 'Indian Restaurant Dublin',
            'canonicalUrl': meta.canonical_url if meta else f"https://amberspice.ie{path if path != '/' else ''}",
            'robots': meta.robots if meta else 'index, follow',
            'openGraph': {
                'title': meta.og_title or (meta.title if meta else ''),
                'description': meta.og_description or (meta.description if meta else ''),
                'image': meta.og_image_url or 'https://amberspice.ie/figma-assets/hero-dish.png',
                'type': meta.og_type if meta else 'restaurant',
            },
            'twitter': {
                'card': 'summary_large_image',
                'title': meta.twitter_title or (meta.title if meta else ''),
                'description': meta.twitter_description or (meta.description if meta else ''),
                'image': meta.twitter_image_url or (meta.og_image_url if meta else 'https://amberspice.ie/figma-assets/hero-dish.png'),
            },
            'structuredData': merged_schema,
        }
        return Response(SEOResolveSerializer(data).data)


class RestaurantSchemaView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: dict}, description="Returns live Schema.org JSON-LD for Amber Spice.")
    def get(self, request):
        return Response(build_restaurant_schema())


class DynamicSitemapView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(description="Generates standard dynamic XML sitemap containing all active pages, categories, and dishes.")
    def get(self, request):
        base_url = request.build_absolute_uri('/')
        xml_content = generate_sitemap_xml(base_url)
        return HttpResponse(xml_content, content_type='application/xml; charset=utf-8')


class DynamicRobotsView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(description="Generates standard robots.txt directives pointing to the live sitemap.")
    def get(self, request):
        base_url = request.build_absolute_uri('/')
        robots_content = generate_robots_txt(base_url)
        return HttpResponse(robots_content, content_type='text/plain; charset=utf-8')


class SEOAuditView(APIView):
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(responses=SEOAuditReportSerializer, description="Audits SEO health across all pages with quality scores.")
    def get(self, request):
        report = audit_seo()
        return Response(SEOAuditReportSerializer(report).data)


class RedirectRuleViewSet(viewsets.ModelViewSet):
    queryset = RedirectRule.objects.all()
    serializer_class = RedirectRuleSerializer
    permission_classes = [permissions.IsAdminUser]
