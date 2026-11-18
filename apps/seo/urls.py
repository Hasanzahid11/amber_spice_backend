from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    SEOMetadataViewSet,
    RestaurantSchemaView,
    SEOAuditView,
    RedirectRuleViewSet,
)

router = DefaultRouter()
router.register('metadata', SEOMetadataViewSet, basename='seo-metadata')
router.register('redirects', RedirectRuleViewSet, basename='seo-redirect')

urlpatterns = [
    path('schema/restaurant/', RestaurantSchemaView.as_view(), name='seo-restaurant-schema'),
    path('audit/', SEOAuditView.as_view(), name='seo-audit'),
    path('', include(router.urls)),
]
