from rest_framework import serializers
from .models import Order, OrderItem
from apps.menu.models import Dish


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            'id',
            'dish',
            'name',
            'quantity',
            'price',
            'station',
            'customizations',
        ]


class OrderItemCreateSerializer(serializers.Serializer):
    dish_id = serializers.IntegerField(required=False, allow_null=True)
    name = serializers.CharField(max_length=200)
    quantity = serializers.IntegerField(default=1, min_value=1)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    station = serializers.CharField(default='curry', required=False)
    customizations = serializers.JSONField(required=False, default=dict)

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        if 'dishId' in data and 'dish_id' not in data:
            data['dish_id'] = data.pop('dishId')
        return super().to_internal_value(data)


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    orderNumber = serializers.CharField(source='order_number', read_only=True)
    customerName = serializers.CharField(source='customer_name')
    customerPhone = serializers.CharField(source='customer_phone', required=False, allow_blank=True)
    diningType = serializers.CharField(source='dining_type')
    tableNumber = serializers.CharField(source='table_number', required=False, allow_null=True, allow_blank=True)
    paymentStatus = serializers.CharField(source='payment_status')
    paymentMethod = serializers.CharField(source='payment_method')
    totalAmount = serializers.DecimalField(source='total_amount', max_digits=10, decimal_places=2)
    deliveryAddress = serializers.CharField(source='delivery_address', required=False, allow_blank=True)
    estimatedTimeMinutes = serializers.IntegerField(source='estimated_time_minutes', required=False)
    elapsedMinutes = serializers.IntegerField(source='elapsed_minutes', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    assignedDeliveryStaff = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id',
            'orderNumber',
            'customer',
            'customerName',
            'customerPhone',
            'diningType',
            'tableNumber',
            'status',
            'paymentStatus',
            'paymentMethod',
            'subtotal',
            'tax',
            'delivery_fee',
            'totalAmount',
            'deliveryAddress',
            'notes',
            'estimatedTimeMinutes',
            'elapsedMinutes',
            'assignedDeliveryStaff',
            'createdAt',
            'items',
        ]

    def get_assignedDeliveryStaff(self, obj):
        if obj.assigned_delivery_staff:
            return {
                'id': obj.assigned_delivery_staff.id,
                'name': obj.assigned_delivery_staff.get_full_name() or obj.assigned_delivery_staff.username,
                'phone': obj.assigned_delivery_staff.phone,
            }
        return None


class OrderCreateSerializer(serializers.ModelSerializer):
    items = OrderItemCreateSerializer(many=True, write_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'customer_name',
            'customer_phone',
            'dining_type',
            'table_number',
            'payment_method',
            'subtotal',
            'tax',
            'delivery_fee',
            'total_amount',
            'delivery_address',
            'notes',
            'estimated_time_minutes',
            'items',
        ]
        read_only_fields = ['id', 'order_number']

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        mapping = {
            'customerName': 'customer_name',
            'customerPhone': 'customer_phone',
            'diningType': 'dining_type',
            'tableNumber': 'table_number',
            'paymentMethod': 'payment_method',
            'deliveryAddress': 'delivery_address',
            'deliveryFee': 'delivery_fee',
            'totalAmount': 'total_amount',
            'estimatedTimeMinutes': 'estimated_time_minutes',
        }
        for camel, snake in mapping.items():
            if camel in data and snake not in data:
                data[snake] = data.pop(camel)
        return super().to_internal_value(data)

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        request = self.context.get('request')
        customer = request.user if request and request.user.is_authenticated else None

        order = Order.objects.create(customer=customer, **validated_data)

        for item_data in items_data:
            dish_id = item_data.pop('dish_id', None)
            dish = Dish.objects.filter(id=dish_id).first() if dish_id else None
            OrderItem.objects.create(order=order, dish=dish, **item_data)

            if dish:
                dish.orders_count += item_data.get('quantity', 1)
                dish.save(update_fields=['orders_count'])

        return order
