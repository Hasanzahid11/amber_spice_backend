from django.core.cache import cache
from django.db.models import F, Sum
from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers
from drf_spectacular.utils import extend_schema, inline_serializer
from datetime import timedelta

from apps.accounts.permissions import CanViewReports
from apps.inventory.models import InventoryItem
from apps.menu.models import Dish
from apps.orders.models import Order
from apps.reservations.models import Table

CACHE_KEY_ANALYTICS_SUMMARY = 'analytics:summary'
CACHE_TIMEOUT = 60 * 5  # 5 minutes


class AnalyticsSummaryView(APIView):
    permission_classes = [CanViewReports]

    @extend_schema(responses=inline_serializer('AnalyticsSummary', fields={
        'totalRevenue': serializers.FloatField(), 'todayRevenue': serializers.FloatField(),
        'totalOrders': serializers.IntegerField(), 'todayOrders': serializers.IntegerField(),
        'activeKitchenOrders': serializers.IntegerField(), 'tables': serializers.DictField(),
        'lowStockAlerts': serializers.IntegerField(), 'topDishes': serializers.ListField(child=serializers.DictField()),
        'dailySales': serializers.ListField(child=serializers.DictField()), 'timestamp': serializers.DateTimeField(),
    }))
    def get(self, request):
        today = timezone.now().date()
        orders_today = Order.objects.filter(created_at__date=today)

        # Revenue
        total_revenue = Order.objects.filter(payment_status='paid').aggregate(
            total=Sum('total_amount')
        )['total'] or 0.0

        today_revenue = orders_today.filter(payment_status='paid').aggregate(
            total=Sum('total_amount')
        )['total'] or 0.0

        # Orders metrics
        total_orders_count = Order.objects.count()
        today_orders_count = orders_today.count()
        active_kitchen_orders = Order.objects.filter(
            status__in=['pending', 'preparing', 'ready']
        ).count()

        # Tables metrics
        total_tables = Table.objects.count()
        occupied_tables = Table.objects.filter(status='occupied').count()
        available_tables = Table.objects.filter(status='available').count()

        # Inventory alerts
        low_stock_count = InventoryItem.objects.filter(
            current_stock__lte=F('minimum_stock')
        ).count()

        # Top dishes
        top_dishes = list(
            Dish.objects.filter(is_available=True)
            .order_by('-orders_count')
            .values('id', 'name', 'price', 'orders_count', 'rating')[:5]
        )

        data = {
            'totalRevenue': float(total_revenue),
            'todayRevenue': float(today_revenue),
            'totalOrders': total_orders_count,
            'todayOrders': today_orders_count,
            'activeKitchenOrders': active_kitchen_orders,
            'tables': {
                'total': total_tables,
                'occupied': occupied_tables,
                'available': available_tables,
            },
            'lowStockAlerts': low_stock_count,
            'topDishes': top_dishes,
            'timestamp': timezone.now().isoformat(),
            'dailySales': [],
        }
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            daily = Order.objects.filter(created_at__date=day)
            revenue = daily.filter(payment_status='paid').aggregate(total=Sum('total_amount'))['total'] or 0
            data['dailySales'].append({'date': day.isoformat(), 'orders': daily.count(), 'revenue': str(revenue)})
        return Response(data)
