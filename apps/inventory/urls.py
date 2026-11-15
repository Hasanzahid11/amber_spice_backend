from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import InventoryCategoryViewSet, InventoryItemViewSet, StockAlertViewSet, WastageViewSet

router = DefaultRouter()
router.register('categories', InventoryCategoryViewSet, basename='inventory-category')
router.register('items', InventoryItemViewSet, basename='inventory-item')
router.register('alerts', StockAlertViewSet, basename='stock-alert')
router.register('wastage', WastageViewSet, basename='wastage')

urlpatterns = [
    path('', include(router.urls)),
]

