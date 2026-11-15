from decimal import Decimal
from rest_framework import serializers
from .models import DailySalesSnapshot, ReportExportLog


class TodayOverviewSerializer(serializers.Serializer):
    todayDate = serializers.DateField()
    totalSales = serializers.DecimalField(max_digits=12, decimal_places=2)
    orderCount = serializers.IntegerField()
    averageOrderValue = serializers.DecimalField(max_digits=10, decimal_places=2)
    deliverySales = serializers.DecimalField(max_digits=12, decimal_places=2)
    deliveryOrderCount = serializers.IntegerField()
    collectionSales = serializers.DecimalField(max_digits=12, decimal_places=2)
    collectionOrderCount = serializers.IntegerField()
    dineInSales = serializers.DecimalField(max_digits=12, decimal_places=2)
    dineInOrderCount = serializers.IntegerField()
    bestSellingProducts = serializers.ListField(child=serializers.DictField())
    lowStockItems = serializers.ListField(child=serializers.DictField())
    pendingOrders = serializers.ListField(child=serializers.DictField())
    activeKitchenCount = serializers.IntegerField()
    tables = serializers.DictField()
    timestamp = serializers.DateTimeField()


class SalesTrendItemSerializer(serializers.Serializer):
    period = serializers.CharField()
    date = serializers.DateField(required=False, allow_null=True)
    totalSales = serializers.DecimalField(max_digits=12, decimal_places=2)
    orderCount = serializers.IntegerField()
    averageOrderValue = serializers.DecimalField(max_digits=10, decimal_places=2)
    deliverySales = serializers.DecimalField(max_digits=12, decimal_places=2)
    collectionSales = serializers.DecimalField(max_digits=12, decimal_places=2)
    dineInSales = serializers.DecimalField(max_digits=12, decimal_places=2)


class ProductSalesSerializer(serializers.Serializer):
    dishId = serializers.IntegerField(allow_null=True)
    name = serializers.CharField()
    category = serializers.CharField()
    unitPrice = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantitySold = serializers.IntegerField()
    totalRevenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    revenuePercentage = serializers.FloatField()
    foodCostPerUnit = serializers.DecimalField(max_digits=10, decimal_places=2)
    totalFoodCost = serializers.DecimalField(max_digits=12, decimal_places=2)
    estimatedGrossMargin = serializers.DecimalField(max_digits=12, decimal_places=2)
    grossMarginPercentage = serializers.FloatField()


class CategorySalesSerializer(serializers.Serializer):
    categoryId = serializers.IntegerField(allow_null=True)
    name = serializers.CharField()
    itemsCount = serializers.IntegerField()
    quantitySold = serializers.IntegerField()
    totalRevenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    revenuePercentage = serializers.FloatField()


class ChannelSalesSerializer(serializers.Serializer):
    channel = serializers.CharField()
    channelCode = serializers.CharField()
    totalSales = serializers.DecimalField(max_digits=12, decimal_places=2)
    orderCount = serializers.IntegerField()
    averageOrderValue = serializers.DecimalField(max_digits=10, decimal_places=2)
    salesPercentage = serializers.FloatField()
    orderPercentage = serializers.FloatField()


class HourlyVolumeSerializer(serializers.Serializer):
    hour = serializers.IntegerField()
    hourDisplay = serializers.CharField()
    orderCount = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=12, decimal_places=2)


class DayOfWeekVolumeSerializer(serializers.Serializer):
    dayOfWeek = serializers.IntegerField()
    dayName = serializers.CharField()
    orderCount = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=12, decimal_places=2)


class BusinessPerformanceSerializer(serializers.Serializer):
    totalRevenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    orderVolume = serializers.IntegerField()
    averageOrderValue = serializers.DecimalField(max_digits=10, decimal_places=2)
    foodCost = serializers.DecimalField(max_digits=12, decimal_places=2)
    foodCostPercentage = serializers.FloatField()
    estimatedGrossMargin = serializers.DecimalField(max_digits=12, decimal_places=2)
    grossMarginPercentage = serializers.FloatField()
    hourlyVolume = HourlyVolumeSerializer(many=True)
    dayOfWeekVolume = DayOfWeekVolumeSerializer(many=True)
    timestamp = serializers.DateTimeField()


class DailySalesSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailySalesSnapshot
        fields = '__all__'


class ReportExportLogSerializer(serializers.ModelSerializer):
    generatedByName = serializers.CharField(source='generated_by.username', read_only=True, default='System')

    class Meta:
        model = ReportExportLog
        fields = '__all__'

