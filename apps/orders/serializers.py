from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers

from .models import Cart, CartItem, CustomerAddress, Order, OrderItem
from apps.menu.models import Dish, DishExtraOption, DishPortionOption
from apps.menu.serializers import DishExtraOptionSerializer, DishPortionOptionSerializer


class CustomerAddressSerializer(serializers.ModelSerializer):
    isDefault = serializers.BooleanField(source='is_default', required=False)
    addressLine1 = serializers.CharField(source='address_line1')
    addressLine2 = serializers.CharField(source='address_line2', required=False, allow_blank=True)
    recipientName = serializers.CharField(source='recipient_name', required=False, allow_blank=True)
    deliveryInstructions = serializers.CharField(source='delivery_instructions', required=False, allow_blank=True)

    class Meta:
        model = CustomerAddress
        fields = [
            'id',
            'label',
            'recipientName',
            'phone',
            'addressLine1',
            'addressLine2',
            'city',
            'eircode',
            'deliveryInstructions',
            'isDefault',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        user = self.context['request'].user
        return CustomerAddress.objects.create(user=user, **validated_data)


class OrderItemSerializer(serializers.ModelSerializer):
    totalPrice = serializers.DecimalField(source='total_price', max_digits=10, decimal_places=2, read_only=True)
    specialInstructions = serializers.CharField(source='special_instructions', required=False, allow_blank=True)

    class Meta:
        model = OrderItem
        fields = [
            'id',
            'dish',
            'name',
            'quantity',
            'price',
            'totalPrice',
            'station',
            'customizations',
            'specialInstructions',
        ]


class OrderItemCreateSerializer(serializers.Serializer):
    dish_id = serializers.IntegerField(required=False, allow_null=True)
    name = serializers.CharField(max_length=200, required=False)
    quantity = serializers.IntegerField(default=1, min_value=1)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    station = serializers.CharField(default='curry', required=False)
    portion_option_id = serializers.IntegerField(required=False, allow_null=True)
    extra_option_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list
    )
    customizations = serializers.JSONField(required=False, default=dict)
    special_instructions = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        dish_id = attrs.get('dish_id')
        dish = Dish.objects.filter(id=dish_id).first() if dish_id else None

        if dish and not attrs.get('name'):
            attrs['name'] = dish.name
        if not attrs.get('name'):
            raise serializers.ValidationError("Item name or valid dish_id is required.")

        # Compute price if not explicitly provided
        if attrs.get('price') is None and dish:
            calculated_price = Decimal(str(dish.price))
            portion_id = attrs.get('portion_option_id')
            if portion_id:
                portion = DishPortionOption.objects.filter(id=portion_id, dish=dish).first()
                if portion:
                    calculated_price += Decimal(str(portion.price_delta))
                    attrs.setdefault('customizations', {})['portion'] = {
                        'id': portion.id,
                        'name': portion.name,
                        'price_delta': float(portion.price_delta)
                    }

            extra_ids = attrs.get('extra_option_ids', [])
            if extra_ids:
                extras = DishExtraOption.objects.filter(id__in=extra_ids, dish=dish)
                extras_data = []
                for extra in extras:
                    calculated_price += Decimal(str(extra.price))
                    extras_data.append({
                        'id': extra.id,
                        'name': extra.name,
                        'price': float(extra.price)
                    })
                attrs.setdefault('customizations', {})['extras'] = extras_data

            attrs['price'] = calculated_price

        if attrs.get('price') is None:
            attrs['price'] = Decimal('0.00')

        if dish and not attrs.get('station'):
            attrs['station'] = dish.station

        return attrs


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    orderNumber = serializers.CharField(source='order_number', read_only=True)
    customerName = serializers.CharField(source='customer_name')
    customerPhone = serializers.CharField(source='customer_phone', required=False, allow_blank=True)
    customerEmail = serializers.CharField(source='customer_email', required=False, allow_blank=True)
    diningType = serializers.CharField(source='dining_type')
    scheduleType = serializers.CharField(source='schedule_type')
    scheduledFor = serializers.DateTimeField(source='scheduled_for', required=False, allow_null=True)
    tableNumber = serializers.CharField(source='table_number', required=False, allow_null=True, allow_blank=True)
    paymentStatus = serializers.CharField(source='payment_status')
    paymentMethod = serializers.CharField(source='payment_method')
    totalAmount = serializers.DecimalField(source='total_amount', max_digits=10, decimal_places=2)
    deliveryFee = serializers.DecimalField(source='delivery_fee', max_digits=10, decimal_places=2)
    deliveryAddress = serializers.CharField(source='delivery_address', required=False, allow_blank=True)
    isSavedOrder = serializers.BooleanField(source='is_saved_order', required=False)
    savedOrderName = serializers.CharField(source='saved_order_name', required=False, allow_blank=True)
    estimatedTimeMinutes = serializers.IntegerField(source='estimated_time_minutes', required=False)
    elapsedMinutes = serializers.IntegerField(source='elapsed_minutes', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    assignedDeliveryStaff = serializers.SerializerMethodField()
    isGuestOrder = serializers.BooleanField(source='is_guest_order', read_only=True)

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
            'scheduleType',
            'scheduledFor',
            'tableNumber',
            'status',
            'paymentStatus',
            'paymentMethod',
            'subtotal',
            'tax',
            'deliveryFee',
            'totalAmount',
            'deliveryAddress',
            'notes',
            'isSavedOrder',
            'savedOrderName',
            'estimatedTimeMinutes',
            'elapsedMinutes',
            'assignedDeliveryStaff',
            'isGuestOrder',
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
    saved_address_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = Order
        fields = [
            'customer_name',
            'customer_phone',
            'customer_email',
            'dining_type',
            'schedule_type',
            'scheduled_for',
            'table_number',
            'payment_method',
            'subtotal',
            'tax',
            'delivery_fee',
            'total_amount',
            'delivery_address',
            'saved_address_id',
            'notes',
            'estimated_time_minutes',
            'items',
        ]
        extra_kwargs = {
            'subtotal': {'required': False},
            'tax': {'required': False},
            'delivery_fee': {'required': False},
            'total_amount': {'required': False},
            'customer_name': {'required': True},
            'customer_phone': {'required': False, 'allow_blank': True},
            'customer_email': {'required': False, 'allow_blank': True},
            'delivery_address': {'required': False, 'allow_blank': True},
        }

    def validate(self, attrs):
        dining_type = attrs.get('dining_type', Order.DiningType.DELIVERY)
        schedule_type = attrs.get('schedule_type', Order.ScheduleType.ASAP)
        scheduled_for = attrs.get('scheduled_for')
        saved_address_id = attrs.get('saved_address_id')
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None

        # 1. Delivery validation
        if dining_type == Order.DiningType.DELIVERY:
            # Check if saved address is chosen
            if saved_address_id and user:
                addr = CustomerAddress.objects.filter(id=saved_address_id, user=user).first()
                if addr:
                    full_addr = f"{addr.address_line1}, {addr.address_line2 + ', ' if addr.address_line2 else ''}{addr.city} ({addr.eircode})".strip()
                    attrs['delivery_address'] = full_addr
                    if not attrs.get('customer_phone') and addr.phone:
                        attrs['customer_phone'] = addr.phone

            if not attrs.get('delivery_address'):
                raise serializers.ValidationError({
                    'delivery_address': "Delivery address is required for delivery orders."
                })

        # 2. Scheduled order validation
        if schedule_type == Order.ScheduleType.SCHEDULED:
            if not scheduled_for:
                raise serializers.ValidationError({
                    'scheduled_for': "scheduled_for date/time is required when schedule_type is 'scheduled'."
                })
            if scheduled_for <= timezone.now():
                raise serializers.ValidationError({
                    'scheduled_for': "Scheduled order time must be in the future."
                })

        # 3. Items validation
        items = attrs.get('items', [])
        if not items:
            raise serializers.ValidationError({'items': "At least one item must be included in the order."})

        # 4. Auto-calculate totals if not passed
        calc_subtotal = Decimal('0.00')
        for it in items:
            q = it.get('quantity', 1)
            p = Decimal(str(it.get('price', 0.00)))
            calc_subtotal += p * q

        calc_delivery_fee = Decimal('3.50') if dining_type == Order.DiningType.DELIVERY else Decimal('0.00')
        calc_tax = Decimal('0.00')
        calc_total = calc_subtotal + calc_delivery_fee + calc_tax

        attrs['subtotal'] = attrs.get('subtotal') or calc_subtotal
        attrs['delivery_fee'] = attrs.get('delivery_fee') if attrs.get('delivery_fee') is not None else calc_delivery_fee
        attrs['tax'] = attrs.get('tax') if attrs.get('tax') is not None else calc_tax
        attrs['total_amount'] = attrs.get('total_amount') or calc_total

        # Set default estimated time
        if not attrs.get('estimated_time_minutes'):
            attrs['estimated_time_minutes'] = 35 if dining_type == Order.DiningType.DELIVERY else 20

        return attrs

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        validated_data.pop('saved_address_id', None)
        request = self.context.get('request')
        customer = request.user if request and request.user.is_authenticated else None

        order = Order.objects.create(customer=customer, **validated_data)

        for item_data in items_data:
            dish_id = item_data.pop('dish_id', None)
            item_data.pop('portion_option_id', None)
            item_data.pop('extra_option_ids', None)
            dish = Dish.objects.filter(id=dish_id).first() if dish_id else None

            OrderItem.objects.create(
                order=order,
                dish=dish,
                **item_data
            )

            if dish:
                dish.orders_count += item_data.get('quantity', 1)
                dish.save(update_fields=['orders_count'])

        return order


class CartItemSerializer(serializers.ModelSerializer):
    dishName = serializers.CharField(source='dish.name', read_only=True)
    dishImage = serializers.CharField(source='dish.image_url', read_only=True)
    unitPrice = serializers.DecimalField(source='unit_price', max_digits=10, decimal_places=2, read_only=True)
    totalPrice = serializers.DecimalField(source='total_price', max_digits=10, decimal_places=2, read_only=True)
    portionOption = DishPortionOptionSerializer(source='portion_option', read_only=True)
    extraOptions = DishExtraOptionSerializer(source='extra_options', many=True, read_only=True)
    specialInstructions = serializers.CharField(source='special_instructions', required=False, allow_blank=True)

    class Meta:
        model = CartItem
        fields = [
            'id',
            'dish',
            'dishName',
            'dishImage',
            'quantity',
            'unitPrice',
            'totalPrice',
            'portionOption',
            'extraOptions',
            'customizations',
            'specialInstructions',
            'created_at',
        ]


class CartItemAddSerializer(serializers.Serializer):
    dish_id = serializers.IntegerField(required=True)
    quantity = serializers.IntegerField(default=1, min_value=1)
    portion_option_id = serializers.IntegerField(required=False, allow_null=True)
    extra_option_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list
    )
    customizations = serializers.JSONField(required=False, default=dict)
    special_instructions = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_dish_id(self, value):
        dish = Dish.objects.filter(id=value).first()
        if not dish:
            raise serializers.ValidationError("Dish not found.")
        if not dish.is_available:
            raise serializers.ValidationError(f"'{dish.name}' is currently unavailable (sold out).")
        return value


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    itemsCount = serializers.IntegerField(source='items_count', read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    deliveryFee = serializers.DecimalField(source='delivery_fee', max_digits=10, decimal_places=2, read_only=True)
    tax = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    totalAmount = serializers.DecimalField(source='total_amount', max_digits=10, decimal_places=2, read_only=True)
    diningType = serializers.CharField(source='dining_type')
    scheduleType = serializers.CharField(source='schedule_type')
    scheduledFor = serializers.DateTimeField(source='scheduled_for', required=False, allow_null=True)

    class Meta:
        model = Cart
        fields = [
            'id',
            'session_id',
            'diningType',
            'scheduleType',
            'scheduledFor',
            'notes',
            'itemsCount',
            'subtotal',
            'deliveryFee',
            'tax',
            'totalAmount',
            'items',
            'updated_at',
        ]


class CheckoutPreviewSerializer(serializers.Serializer):
    """
    Computes exact checkout totals before placing order.
    """
    dining_type = serializers.ChoiceField(choices=Order.DiningType.choices, default=Order.DiningType.DELIVERY)
    schedule_type = serializers.ChoiceField(choices=Order.ScheduleType.choices, default=Order.ScheduleType.ASAP)
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)
    items = OrderItemCreateSerializer(many=True, required=False, default=list)
