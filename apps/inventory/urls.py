from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import InventoryCategoryViewSet, InventoryItemViewSet

router = DefaultRouter()
router.register('categories', InventoryCategoryViewSet, basename='inventory-category')
router.register('items', InventoryItemViewSet, basename='inventory-item')

urlpatterns = [
    path('', include(router.urls)),
]

