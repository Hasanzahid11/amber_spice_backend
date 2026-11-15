from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from apps.seo.views import SitemapXMLView, RobotsTxtView

urlpatterns = [
    path('admin/', admin.site.urls),

    # OpenAPI 3 Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # API v1 Endpoints
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/menu/', include('apps.menu.urls')),
    path('api/v1/orders/', include('apps.orders.urls')),
    path('api/v1/kitchen/', include('apps.kitchen.urls')),
    path('api/v1/reservations/', include('apps.reservations.urls')),
    path('api/v1/inventory/', include('apps.inventory.urls')),
    path('api/v1/staff/', include('apps.staff.urls')),
    path('api/v1/analytics/', include('apps.analytics.urls')),
    path('api/v1/promotions/', include('apps.promotions.urls')),
    path('api/v1/notifications/', include('apps.notifications.urls')),
    path('api/v1/stock/', include('apps.stock.urls')),
    path('api/v1/seo/', include('apps.seo.urls')),
    path('api/v1/restaurant/', include('apps.restaurant.urls')),

    # Root Crawler Directives
    path('sitemap.xml', SitemapXMLView.as_view(), name='root-sitemap-xml'),
    path('robots.txt', RobotsTxtView.as_view(), name='root-robots-txt'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
