from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    StockOperationsView,
    StockValuationView,
    StockHistoryView,
    StockAlertsScanView,
    FoodCostProfitabilityView,
    SupplierManagementViewSet,
    PurchaseOrderViewSet,
    StockTransferViewSet,
    StockAuditCountViewSet,
    StockWastageViewSet,
)

router = DefaultRouter()
router.register(r'suppliers', SupplierManagementViewSet, basename='stock-suppliers')
router.register(r'purchase-orders', PurchaseOrderViewSet, basename='stock-purchase-orders')
router.register(r'transfers', StockTransferViewSet, basename='stock-transfers')
router.register(r'audits', StockAuditCountViewSet, basename='stock-audits')
router.register(r'wastage-logs', StockWastageViewSet, basename='stock-wastage-logs')

urlpatterns = [
    # Stock Operations (Add, Remove, Adjust, Record Wastage)
    path('add/', StockOperationsView.as_view(), {'operation': 'add'}, name='stock-add'),
    path('remove/', StockOperationsView.as_view(), {'operation': 'remove'}, name='stock-remove'),
    path('adjust/', StockOperationsView.as_view(), {'operation': 'adjust'}, name='stock-adjust'),
    path('wastage/', StockOperationsView.as_view(), {'operation': 'wastage'}, name='stock-wastage'),

    # Valuation & Movement History
    path('valuation/', StockValuationView.as_view(), name='stock-valuation'),
    path('history/', StockHistoryView.as_view(), name='stock-history'),
    path('check-alerts/', StockAlertsScanView.as_view(), name='stock-check-alerts'),

    # Food Cost & Profitability Analysis
    path('profitability/', FoodCostProfitabilityView.as_view(), name='stock-profitability'),

    path('', include(router.urls)),
]

