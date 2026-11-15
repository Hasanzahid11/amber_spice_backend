from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    KitchenStationViewSet,
    KitchenScreenViewSet,
    KitchenDisplayViewSet,
    KitchenBumpLogViewSet,
)

router = DefaultRouter()
router.register(r'stations', KitchenStationViewSet, basename='kitchen-stations')
router.register(r'screens', KitchenScreenViewSet, basename='kitchen-screens')
router.register(r'tickets', KitchenDisplayViewSet, basename='kitchen-tickets')
router.register(r'orders', KitchenDisplayViewSet, basename='kitchen-orders')
router.register(r'logs', KitchenBumpLogViewSet, basename='kitchen-logs')

urlpatterns = [
    # Convenient top-level shortcuts
    path('summary/', KitchenDisplayViewSet.as_view({'get': 'summary'}), name='kitchen-summary'),
    path('', include(router.urls)),
]

