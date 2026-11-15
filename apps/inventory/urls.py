from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    CalculateConsumptionView,
    DeductOrderInventoryView,
    InventoryItemViewSet,
    RecipeViewSet,
    StockMovementViewSet,
    SupplierViewSet,
)

router = DefaultRouter()
router.register('items', InventoryItemViewSet, basename='inventory-item')
router.register('suppliers', SupplierViewSet, basename='supplier')
router.register('recipes', RecipeViewSet, basename='recipe')
router.register('movements', StockMovementViewSet, basename='stock-movement')

urlpatterns = [
    path('calculate-consumption/', CalculateConsumptionView.as_view(), name='inventory-calculate-consumption'),
    path('deduct-order/', DeductOrderInventoryView.as_view(), name='inventory-deduct-order'),
    # Direct alias for low stock check
    path('low-stock/', InventoryItemViewSet.as_view({'get': 'low_stock'}), name='inventory-low-stock-alias'),
    path('low_stock/', InventoryItemViewSet.as_view({'get': 'low_stock'}), name='inventory-low-stock-alias-underscore'),
    path('', include(router.urls)),
]
