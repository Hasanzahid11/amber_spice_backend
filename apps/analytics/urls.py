from django.urls import path
from .views import (
    AnalyticsSummaryView,
    DashboardOverviewView,
    SalesAnalyticsView,
    ProductSalesAnalyticsView,
    CategorySalesAnalyticsView,
    ChannelSalesAnalyticsView,
    BusinessPerformanceAnalyticsView,
    ReportExportView,
    ReportExportLogsView,
)

urlpatterns = [
    # Legacy & Enriched Summary
    path('summary/', AnalyticsSummaryView.as_view(), name='analytics-summary'),

    # Executive Today's Dashboard
    path('dashboard/', DashboardOverviewView.as_view(), name='analytics-dashboard'),

    # Business Analytics
    path('sales/', SalesAnalyticsView.as_view(), name='analytics-sales'),
    path('products/', ProductSalesAnalyticsView.as_view(), name='analytics-products'),
    path('categories/', CategorySalesAnalyticsView.as_view(), name='analytics-categories'),
    path('channels/', ChannelSalesAnalyticsView.as_view(), name='analytics-channels'),
    path('performance/', BusinessPerformanceAnalyticsView.as_view(), name='analytics-performance'),

    # Report Exports (CSV / Excel / PDF / HTML)
    path('reports/export/', ReportExportView.as_view(), name='analytics-reports-export'),
    path('reports/logs/', ReportExportLogsView.as_view(), name='analytics-reports-logs'),
]
