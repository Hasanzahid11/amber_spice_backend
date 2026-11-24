from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from .models import Order, OrderItem, OrderEvent
from apps.menu.models import Dish
from .pricing import price_items, apply_promotion, checkout_policy
from .delivery_serializers import DeliverySummarySerializer
from .delivery_chat import ContactRiderSerializer, contact_available


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
    dish_id = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=200, required=False)
    quantity = serializers.IntegerField(default=1, min_value=1)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    station = serializers.CharField(default='curry', required=False)
    customizations = serializers.JSONField(required=False, default=dict)

    def validate_customizations(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('Customizations must be an object.')
        return value

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        if 'dishId' in data and 'dish_id' not in data:
            data['dish_id'] = data.pop('dishId')
        return super().to_internal_value(data)


class OrderEventSerializer(serializers.ModelSerializer):
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = OrderEvent
        fields = ['status', 'createdAt']


class DeliveryStaffSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    phone = serializers.CharField(allow_blank=True)
    onDuty = serializers.BooleanField()
    activeJobs = serializers.IntegerField()


class OrderSerializer(serializers.ModelSerializer):
    riderContactAvailable = serializers.SerializerMethodField()
    deliveryProgress = DeliverySummarySerializer(source='delivery_job', read_only=True, allow_null=True)
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
    customerEmail = serializers.EmailField(source='customer_email', read_only=True)
    deliveryFee = serializers.DecimalField(source='delivery_fee', max_digits=10, decimal_places=2, read_only=True)
    discountAmount = serializers.DecimalField(source='discount_amount', max_digits=10, decimal_places=2, read_only=True)
    couponCode = serializers.CharField(source='coupon_code', read_only=True)
    scheduledFor = serializers.DateTimeField(source='scheduled_for', read_only=True)
    pickupCode = serializers.CharField(source='display_pickup_code', read_only=True)
    pickupRack = serializers.CharField(source='pickup_rack', read_only=True)
    customerArrivedAt = serializers.DateTimeField(source='customer_arrived_at', read_only=True)
    pickedUpAt = serializers.DateTimeField(source='picked_up_at', read_only=True)
    paymentCollectedAt = serializers.DateTimeField(source='payment_collected_at', read_only=True)
    paymentCollectedByName = serializers.SerializerMethodField()
    counterNotes = serializers.CharField(source='counter_notes', read_only=True)
    events = OrderEventSerializer(many=True, read_only=True)

    def get_paymentCollectedByName(self, obj) -> str:
        if obj.payment_collected_by:
            return obj.payment_collected_by.get_full_name() or obj.payment_collected_by.username
        return ''

    class Meta:
        model = Order
        fields = [
            'id',
            'orderNumber',
            'customer',
            'customerName',
            'customerPhone',
            'customerEmail',
            'diningType',
            'tableNumber',
            'pickupCode',
            'pickupRack',
            'customerArrivedAt',
            'pickedUpAt',
            'paymentCollectedAt',
            'paymentCollectedByName',
            'counterNotes',
            'status',
            'paymentStatus',
            'paymentMethod',
            'subtotal',
            'tax',
            'delivery_fee',
            'deliveryFee',
            'discountAmount',
            'couponCode',
            'scheduledFor',
            'events',
            'totalAmount',
            'deliveryAddress',
            'notes',
            'estimatedTimeMinutes',
            'elapsedMinutes',
            'assignedDeliveryStaff',
            'createdAt',
            'items',
            'deliveryProgress',
            'riderContactAvailable',
        ]

    def get_riderContactAvailable(self, obj) -> bool:
        return contact_available(obj)

    @extend_schema_field(ContactRiderSerializer(allow_null=True))
    def get_assignedDeliveryStaff(self, obj):
        if obj.assigned_delivery_staff:
            rider = obj.assigned_delivery_staff
            profile = getattr(rider, 'rider_profile', None)
            return {
                'id': rider.id,
                'name': rider.get_full_name() or rider.username,
                'phone': (rider.phone or '') if contact_available(obj) else '',
                'avatar': rider.avatar or '',
                'vehicleType': profile.vehicle_type if profile else '',
                'vehicleRegistration': profile.vehicle_registration if profile else '',
            }
        return None

class OrderQuoteSerializer(serializers.Serializer):
    items = OrderItemCreateSerializer(many=True, allow_empty=False, max_length=100)
    dining_type = serializers.ChoiceField(choices=Order.DiningType.choices, default='delivery')
    coupon_code = serializers.CharField(required=False, allow_blank=True, max_length=40)

    def to_internal_value(self, data):
        data = data.copy()
        if 'diningType' in data:
            data['dining_type'] = data.pop('diningType')
        if 'couponCode' in data:
            data['coupon_code'] = data.pop('couponCode')
        return super().to_internal_value(data)

    def validate(self, attrs):
        # Validate catalog selections even for quote requests.
        _, totals = price_items(attrs['items'], attrs['dining_type'])
        apply_promotion(totals, attrs.get('coupon_code'), self.context.get('request').user if self.context.get('request') else None)
        return attrs


class OrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)


class DeliveryAssignmentSerializer(serializers.Serializer):
    delivery_staff_id = serializers.IntegerField(min_value=1)


class CashCollectionSerializer(serializers.Serializer):
    payment_status = serializers.ChoiceField(choices=['paid'])


class OrderCreateSerializer(serializers.ModelSerializer):
    items = OrderItemCreateSerializer(many=True, write_only=True, allow_empty=False, max_length=100)
    client_request_id = serializers.UUIDField(required=False)

    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'customer_name',
            'customer_phone',
            'customer_email',
            'coupon_code',
            'client_request_id',
            'scheduled_for',
            'dining_type',
            'table_number',
            'payment_method',
            'subtotal',
            'tax',
            'delivery_fee',
            'total_amount',
            'delivery_address',
            'delivery_postal_code',
            'notes',
            'pickup_rack',
            'estimated_time_minutes',
            'items',
        ]
        read_only_fields = ['id', 'order_number', 'subtotal', 'tax', 'delivery_fee', 'estimated_time_minutes']
        extra_kwargs = {'total_amount': {'required': False}}

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        mapping = {
            'customerName': 'customer_name',
            'customerPhone': 'customer_phone',
            'customerEmail': 'customer_email',
            'couponCode': 'coupon_code',
            'clientRequestId': 'client_request_id',
            'scheduledFor': 'scheduled_for',
            'diningType': 'dining_type',
            'tableNumber': 'table_number',
            'pickupRack': 'pickup_rack',
            'paymentMethod': 'payment_method',
            'deliveryAddress': 'delivery_address',
            'deliveryPostalCode': 'delivery_postal_code',
            'deliveryFee': 'delivery_fee',
            'totalAmount': 'total_amount',
            'estimatedTimeMinutes': 'estimated_time_minutes',
        }
        for camel, snake in mapping.items():
            if camel in data and snake not in data:
                data[snake] = data.pop(camel)
        return super().to_internal_value(data)

    def validate(self, attrs):
        dining_type = attrs.get('dining_type', 'dine-in')
        if dining_type == 'delivery':
            for field in ['delivery_address', 'customer_phone']:
                if not attrs.get(field, '').strip():
                    raise serializers.ValidationError({field: 'Required for delivery.'})
            profile = checkout_policy()
            if profile and profile.delivery_postcode_prefixes:
                postcode = attrs.get('delivery_postal_code', '').upper().replace(' ', '')
                if not postcode.startswith(tuple(profile.delivery_postcode_prefixes)):
                    raise serializers.ValidationError({'delivery_postal_code': 'This address is outside the configured delivery area. Select collection or another address.'})
        if dining_type == 'dine-in' and not attrs.get('table_number'):
            raise serializers.ValidationError({'table_number': 'Select a table for dine-in.'})
        if dining_type == 'dine-in':
            from apps.reservations.models import Table
            if not Table.objects.filter(number=attrs['table_number']).exists():
                raise serializers.ValidationError({'table_number': 'Select an existing restaurant table.'})
        if attrs.get('payment_method', 'cash') != 'cash':
            raise serializers.ValidationError({'payment_method': 'Online payments are not configured. Select cash.'})
        if attrs.get('scheduled_for') and attrs['scheduled_for'] <= timezone.now():
            raise serializers.ValidationError({'scheduled_for': 'Select a future date and time.'})
        _, totals = price_items(attrs['items'], dining_type)
        totals, _ = apply_promotion(totals, attrs.get('coupon_code'), self.context.get('request').user if self.context.get('request') else None)
        if 'total_amount' in attrs and attrs['total_amount'] != totals['total_amount']:
            raise serializers.ValidationError({'total_amount': 'Prices have changed. Refresh the quote and confirm again.'})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        request = self.context.get('request')
        customer = request.user if request and request.user.is_authenticated else None

        priced_items, totals = price_items(items_data, validated_data.get('dining_type', 'dine-in'))
        totals, promotion = apply_promotion(totals, validated_data.get('coupon_code'), customer, lock=True)
        if 'total_amount' in validated_data and validated_data['total_amount'] != totals['total_amount']:
            raise serializers.ValidationError({'total_amount': 'The quote changed. Refresh and confirm again.'})
        if promotion:
            promotion.usage_count = F('usage_count') + 1
            promotion.save(update_fields=['usage_count'])
            validated_data['coupon_code'] = promotion.code
        validated_data.update(totals)
        order = Order.objects.create(customer=customer, **validated_data)
        if order.dining_type == 'dine-in':
            from apps.reservations.models import Table
            table = Table.objects.select_for_update().get(number=order.table_number)
            table.status = 'occupied'
            table.guest_name = order.customer_name
            table.current_order = order.order_number
            table.save(update_fields=['status', 'guest_name', 'current_order'])
        for item_data in priced_items:
            OrderItem.objects.create(order=order, **item_data)
            Dish.objects.filter(pk=item_data['dish'].pk).update(orders_count=F('orders_count') + item_data['quantity'])
        OrderEvent.objects.create(order=order, status=order.status)
        try:
            from apps.inventory.services import deplete_order_inventory
            deplete_order_inventory(order, user=customer)
        except Exception:
            pass
        return order


class CheckoutResponseSerializer(OrderSerializer):
    customerContactToken = serializers.UUIDField(required=False, read_only=True, help_text="Guest checkout only: private delivery-chat credential. Keep it in the original browser; never print it on bag tickets or use it in URLs. Linked orders use owner JWT.")

    class Meta(OrderSerializer.Meta):
        fields = [*OrderSerializer.Meta.fields, 'customerContactToken']
