from rest_framework import serializers
from django.utils import timezone
from apps.orders.models import Order, OrderItem
from .models import KitchenStation, KitchenScreen, KitchenBumpLog


class KitchenStationSerializer(serializers.ModelSerializer):
    active_orders_count = serializers.SerializerMethodField()

    class Meta:
        model = KitchenStation
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'color_code',
            'display_order',
            'is_active',
            'default_prep_time_minutes',
            'printer_ip',
            'active_orders_count',
            'created_at',
            'updated_at',
        ]

    def get_active_orders_count(self, obj) -> int:
        active_statuses = [Order.Status.PENDING, Order.Status.PREPARING]
        return Order.objects.filter(
            status__in=active_statuses,
            items__station=obj.slug
        ).distinct().count()


class KitchenScreenSerializer(serializers.ModelSerializer):
    station_name = serializers.CharField(source='station.name', read_only=True, default=None)
    station_slug = serializers.CharField(source='station.slug', read_only=True, default=None)

    class Meta:
        model = KitchenScreen
        fields = [
            'id',
            'name',
            'screen_type',
            'station',
            'station_name',
            'station_slug',
            'device_identifier',
            'auto_refresh_seconds',
            'warning_threshold_pct',
            'critical_delay_minutes',
            'sound_alerts_enabled',
            'is_active',
            'created_at',
            'updated_at',
        ]


class KitchenBumpLogSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True, default=None)
    station_name = serializers.CharField(source='station.name', read_only=True, default=None)
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = KitchenBumpLog
        fields = [
            'id',
            'order',
            'order_number',
            'action',
            'action_display',
            'item',
            'item_name',
            'station',
            'station_name',
            'performed_by',
            'performed_by_name',
            'from_status',
            'to_status',
            'notes',
            'created_at',
        ]

    def get_performed_by_name(self, obj) -> str:
        if obj.performed_by:
            return obj.performed_by.get_full_name() or obj.performed_by.username
        return 'System'


class KitchenOrderItemSerializer(serializers.ModelSerializer):
    portion = serializers.SerializerMethodField()
    extras = serializers.SerializerMethodField()
    modifiers = serializers.SerializerMethodField()
    removedIngredients = serializers.SerializerMethodField()
    addedIngredients = serializers.SerializerMethodField()
    isReady = serializers.BooleanField(source='is_ready')
    preparedAt = serializers.DateTimeField(source='prepared_at', allow_null=True)
    specialInstructions = serializers.CharField(source='special_instructions', allow_blank=True)

    class Meta:
        model = OrderItem
        fields = [
            'id',
            'name',
            'quantity',
            'price',
            'station',
            'portion',
            'extras',
            'modifiers',
            'removedIngredients',
            'addedIngredients',
            'specialInstructions',
            'isReady',
            'preparedAt',
        ]

    def get_portion(self, obj) -> str:
        customs = obj.customizations or {}
        return customs.get('portion', 'Regular')

    def get_extras(self, obj) -> list:
        customs = obj.customizations or {}
        return customs.get('extras', [])

    def get_modifiers(self, obj) -> dict:
        customs = obj.customizations or {}
        return customs.get('modifiers', {})

    def get_removedIngredients(self, obj) -> list:
        customs = obj.customizations or {}
        return customs.get('removed_ingredients', [])

    def get_addedIngredients(self, obj) -> list:
        customs = obj.customizations or {}
        return customs.get('added_ingredients', [])


class KitchenTicketSerializer(serializers.ModelSerializer):
    """
    Dedicated KDS Ticket serializer tailored for kitchen display screens.
    Includes time elapsed, target completion, delay calculation, urgency status, and items list.
    """
    orderNumber = serializers.CharField(source='order_number', read_only=True)
    statusDisplay = serializers.CharField(source='get_status_display', read_only=True)
    diningType = serializers.CharField(source='dining_type')
    diningTypeDisplay = serializers.CharField(source='get_dining_type_display', read_only=True)
    scheduleType = serializers.CharField(source='schedule_type')
    scheduledFor = serializers.DateTimeField(source='scheduled_for', allow_null=True)
    tableNumber = serializers.CharField(source='table_number', allow_blank=True)
    customerName = serializers.CharField(source='customer_name')
    customerPhone = serializers.CharField(source='customer_phone')
    deliveryAddress = serializers.CharField(source='delivery_address', allow_blank=True)
    priority = serializers.CharField()
    priorityDisplay = serializers.CharField(source='get_priority_display', read_only=True)
    estimatedTimeMinutes = serializers.IntegerField(source='estimated_time_minutes')
    elapsedMinutes = serializers.IntegerField(read_only=True)
    timeRemainingMinutes = serializers.IntegerField(read_only=True)
    targetCompletionTime = serializers.DateTimeField(read_only=True)
    isDelayed = serializers.BooleanField(source='is_delayed', read_only=True)
    delayMinutes = serializers.IntegerField(source='delay_minutes', read_only=True)
    delaySeverity = serializers.CharField(source='delay_severity', read_only=True)
    totalItemsCount = serializers.SerializerMethodField()
    readyItemsCount = serializers.SerializerMethodField()
    allReady = serializers.SerializerMethodField()
    preparedAt = serializers.DateTimeField(source='prepared_at', allow_null=True)
    readyAt = serializers.DateTimeField(source='ready_at', allow_null=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    items = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id',
            'orderNumber',
            'status',
            'statusDisplay',
            'diningType',
            'diningTypeDisplay',
            'scheduleType',
            'scheduledFor',
            'tableNumber',
            'customerName',
            'customerPhone',
            'deliveryAddress',
            'priority',
            'priorityDisplay',
            'estimatedTimeMinutes',
            'elapsedMinutes',
            'timeRemainingMinutes',
            'targetCompletionTime',
            'isDelayed',
            'delayMinutes',
            'delaySeverity',
            'totalItemsCount',
            'readyItemsCount',
            'allReady',
            'notes',
            'preparedAt',
            'readyAt',
            'createdAt',
            'items',
        ]

    def get_items(self, obj):
        station_filter = self.context.get('station_filter')
        items_qs = obj.items.all()
        if station_filter and station_filter != 'all':
            items_qs = items_qs.filter(station=station_filter)
        return KitchenOrderItemSerializer(items_qs, many=True).data

    def get_totalItemsCount(self, obj) -> int:
        return obj.items.count()

    def get_readyItemsCount(self, obj) -> int:
        return obj.items.filter(is_ready=True).count()

    def get_allReady(self, obj) -> bool:
        total = obj.items.count()
        return total > 0 and self.get_readyItemsCount(obj) == total


class KitchenSummarySerializer(serializers.Serializer):
    totalActiveOrders = serializers.IntegerField()
    newOrdersCount = serializers.IntegerField()
    preparingOrdersCount = serializers.IntegerField()
    readyOrdersCount = serializers.IntegerField()
    delayedOrdersCount = serializers.IntegerField()
    criticalDelayedOrdersCount = serializers.IntegerField()
    urgentPriorityCount = serializers.IntegerField()
    averagePrepTimeMinutes = serializers.FloatField()
    timestamp = serializers.DateTimeField()

