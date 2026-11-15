from datetime import datetime
from django.core.cache import cache
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import CanViewReports
from .models import DailySalesSnapshot, ReportExportLog
from .serializers import (
    TodayOverviewSerializer,
    ProductSalesSerializer,
    CategorySalesSerializer,
    ChannelSalesSerializer,
    BusinessPerformanceSerializer,
    DailySalesSnapshotSerializer,
    ReportExportLogSerializer,
)
from .services import (
    get_today_overview,
    get_sales_analytics,
    get_sales_by_product,
    get_sales_by_category,
    get_sales_by_channel,
    get_business_performance,
    generate_report_csv,
    generate_report_html,
)

CACHE_KEY_ANALYTICS_SUMMARY = 'analytics:summary'
CACHE_TIMEOUT = 60 * 3  # 3 minutes


def parse_date_param(param_val):
    if not param_val:
        return None
    try:
        return datetime.strptime(param_val, '%Y-%m-%d').date()
    except ValueError:
        return None


class AnalyticsSummaryView(APIView):
    """
    GET /api/v1/analytics/summary/
    Maintains 100% backward compatibility with existing API while enriching
    the payload with complete today's overview, channel sales, and inventory alerts.
    """
    permission_classes = [CanViewReports]

    def get(self, request):
        today_data = get_today_overview()

        # Build composite payload retaining original keys and adding new requested keys
        data = {
            # Legacy keys (preserved for backward compatibility)
            'totalRevenue': float(today_data['totalSales']),
            'todayRevenue': float(today_data['totalSales']),
            'totalOrders': today_data['orderCount'],
            'todayOrders': today_data['orderCount'],
            'activeKitchenOrders': today_data['activeKitchenCount'],
            'tables': today_data['tables'],
            'lowStockAlerts': len(today_data['lowStockItems']),
            'topDishes': today_data['bestSellingProducts'][:5],
            'timestamp': today_data['timestamp'].isoformat(),

            # New comprehensive Today's Overview fields
            'todayOverview': {
                'totalSales': float(today_data['totalSales']),
                'orderCount': today_data['orderCount'],
                'averageOrderValue': float(today_data['averageOrderValue']),
                'deliverySales': float(today_data['deliverySales']),
                'deliveryOrderCount': today_data['deliveryOrderCount'],
                'collectionSales': float(today_data['collectionSales']),
                'collectionOrderCount': today_data['collectionOrderCount'],
                'dineInSales': float(today_data['dineInSales']),
                'dineInOrderCount': today_data['dineInOrderCount'],
                'bestSellingProducts': today_data['bestSellingProducts'],
                'currentLowStockItems': today_data['lowStockItems'],
                'pendingOrders': today_data['pendingOrders'],
                'activeKitchenOrders': today_data['activeKitchenCount'],
            }
        }
        return Response(data)


class DashboardOverviewView(APIView):
    """
    GET /api/v1/analytics/dashboard/
    Dedicated central dashboard endpoint for restaurant Owner/Admin.
    Returns:
    - Today's total sales
    - Number of orders
    - Average order value (AOV)
    - Delivery sales & orders
    - Collection / takeaway sales & orders
    - Dine-in sales & orders
    - Best-selling products today
    - Current low-stock items
    - Pending incoming orders
    - Table occupancy
    """
    permission_classes = [CanViewReports]

    def get(self, request):
        overview = get_today_overview()
        serializer = TodayOverviewSerializer(overview)
        return Response(serializer.data)


class SalesAnalyticsView(APIView):
    """
    GET /api/v1/analytics/sales/
    Query parameters:
    - period: 'daily' | 'weekly' | 'monthly' (default: 'daily')
    - start_date: 'YYYY-MM-DD'
    - end_date: 'YYYY-MM-DD'
    Returns time-series revenue, order counts, AOV, and channel breakdown.
    """
    permission_classes = [CanViewReports]

    def get(self, request):
        period = request.query_params.get('period', 'daily').lower()
        if period not in ['daily', 'weekly', 'monthly']:
            period = 'daily'

        start_date = parse_date_param(request.query_params.get('start_date'))
        end_date = parse_date_param(request.query_params.get('end_date'))

        data = get_sales_analytics(period=period, start_date=start_date, end_date=end_date)
        return Response(data)


class ProductSalesAnalyticsView(APIView):
    """
    GET /api/v1/analytics/products/
    Returns sales by product with quantities, revenue, food cost per portion, and gross margins.
    """
    permission_classes = [CanViewReports]

    def get(self, request):
        start_date = parse_date_param(request.query_params.get('start_date'))
        end_date = parse_date_param(request.query_params.get('end_date'))

        products = get_sales_by_product(start_date=start_date, end_date=end_date)
        serializer = ProductSalesSerializer(products, many=True)
        return Response(serializer.data)


class CategorySalesAnalyticsView(APIView):
    """
    GET /api/v1/analytics/categories/
    Returns sales aggregated by menu category.
    """
    permission_classes = [CanViewReports]

    def get(self, request):
        start_date = parse_date_param(request.query_params.get('start_date'))
        end_date = parse_date_param(request.query_params.get('end_date'))

        categories = get_sales_by_category(start_date=start_date, end_date=end_date)
        serializer = CategorySalesSerializer(categories, many=True)
        return Response(serializer.data)


class ChannelSalesAnalyticsView(APIView):
    """
    GET /api/v1/analytics/channels/
    Returns sales split by delivery, takeaway/collection, and dine-in.
    """
    permission_classes = [CanViewReports]

    def get(self, request):
        start_date = parse_date_param(request.query_params.get('start_date'))
        end_date = parse_date_param(request.query_params.get('end_date'))

        channels = get_sales_by_channel(start_date=start_date, end_date=end_date)
        serializer = ChannelSalesSerializer(channels, many=True)
        return Response(serializer.data)


class BusinessPerformanceAnalyticsView(APIView):
    """
    GET /api/v1/analytics/performance/
    Returns high-level business performance metrics:
    - Total revenue & order volume
    - Average order value (AOV)
    - Food cost & Food cost percentage
    - Estimated gross margin & margin percentage
    - Hourly volume distribution (peak hours)
    - Day of week trends
    """
    permission_classes = [CanViewReports]

    def get(self, request):
        start_date = parse_date_param(request.query_params.get('start_date'))
        end_date = parse_date_param(request.query_params.get('end_date'))

        perf = get_business_performance(start_date=start_date, end_date=end_date)
        serializer = BusinessPerformanceSerializer(perf)
        return Response(serializer.data)


class ReportExportView(APIView):
    """
    GET /api/v1/analytics/reports/export/
    Query parameters:
    - report_type: 'daily_sales' | 'sales_by_product' | 'sales_by_category' | 'sales_by_channel' | 'low_stock_items'
    - format: 'csv' | 'excel' | 'pdf' | 'html' (default: 'csv')
    - start_date: 'YYYY-MM-DD'
    - end_date: 'YYYY-MM-DD'
    Exports reports as downloadable CSV, Excel-compatible sheets, or printable PDF-ready HTML.
    """
    permission_classes = [CanViewReports]

    def get(self, request):
        report_type = request.query_params.get('report_type', 'daily_sales').lower()
        export_format = request.query_params.get('format', 'csv').lower()
        start_date = parse_date_param(request.query_params.get('start_date'))
        end_date = parse_date_param(request.query_params.get('end_date'))

        if export_format in ['html', 'pdf']:
            html_content = generate_report_html(report_type, start_date=start_date, end_date=end_date)

            # Audit log
            ReportExportLog.objects.create(
                report_type=report_type,
                export_format=export_format,
                generated_by=request.user if request.user.is_authenticated else None,
                start_date=start_date,
                end_date=end_date,
                row_count=1
            )
            return HttpResponse(html_content, content_type='text/html')

        # CSV / Excel
        csv_content, count = generate_report_csv(report_type, start_date=start_date, end_date=end_date)

        # Audit log
        ReportExportLog.objects.create(
            report_type=report_type,
            export_format=export_format,
            generated_by=request.user if request.user.is_authenticated else None,
            start_date=start_date,
            end_date=end_date,
            row_count=count
        )

        date_stamp = timezone.now().strftime('%Y%m%d_%H%M')
        filename = f"{report_type}_{date_stamp}"

        if export_format == 'excel':
            response = HttpResponse(csv_content, content_type='application/vnd.ms-excel; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}.xls"'
        else:
            response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'

        return response


class ReportExportLogsView(APIView):
    """
    GET /api/v1/analytics/reports/logs/
    Returns list of recently generated report exports.
    """
    permission_classes = [CanViewReports]

    def get(self, request):
        logs = ReportExportLog.objects.select_related('generated_by').all()[:50]
        serializer = ReportExportLogSerializer(logs, many=True)
        return Response(serializer.data)
