from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    PageSEODataView,
    LocalSEODataView,
    RestaurantSchemaView,
    MenuSchemaView,
    SitemapXMLView,
    RobotsTxtView,
    RestaurantSEOProfileView,
    PageSEOMetadataViewSet,
    MarketingCampaignViewSet,
    OptimizedImageViewSet,
)

router = DefaultRouter()
router.register(r'pages', PageSEOMetadataViewSet, basename='seo-pages')
router.register(r'campaigns', MarketingCampaignViewSet, basename='seo-campaigns')
router.register(r'images', OptimizedImageViewSet, basename='seo-images')

urlpatterns = [
    # Public Metadata & Schema APIs
    path('metadata/', PageSEODataView.as_view(), name='seo-metadata'),
    path('local/', LocalSEODataView.as_view(), name='seo-local'),
    path('schema/restaurant/', RestaurantSchemaView.as_view(), name='seo-schema-restaurant'),
    path('schema/menu/', MenuSchemaView.as_view(), name='seo-schema-menu'),

    # XML Sitemap & Robots.txt
    path('sitemap.xml', SitemapXMLView.as_view(), name='seo-sitemap-xml'),
    path('sitemap/', SitemapXMLView.as_view(), name='seo-sitemap'),
    path('robots.txt', RobotsTxtView.as_view(), name='seo-robots-txt'),
    path('robots/', RobotsTxtView.as_view(), name='seo-robots'),

    # Global SEO & Google Business Profile
    path('profile/', RestaurantSEOProfileView.as_view(), name='seo-profile'),

    path('', include(router.urls)),
]

