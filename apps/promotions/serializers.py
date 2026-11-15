from decimal import Decimal
from rest_framework import serializers
from .models import Promotion, PromotionUsage


class PromotionSerializer(serializers.ModelSerializer):
    """
    Admin & Manager serializer for full CRUD on promotions and discounts.
    """
    isExpired = serializers.BooleanField(source='is_expired', read_only=True)
    isStarted = serializers.BooleanField(source='is_started', read_only=True)
    isLimitReached = serializers.BooleanField(source='is_limit_reached', read_only=True)
    totalDiscountGiven = serializers.SerializerMethodField()
    categoryNames = serializers.SerializerMethodField()
    dishNames = serializers.SerializerMethodField()
    buyDishName = serializers.CharField(source='buy_dish.name', read_only=True, default=None)
    getDishName = serializers.CharField(source='get_dish.name', read_only=True, default=None)

    class Meta:
        model = Promotion
        fields = [
            'id',
            'name',
            'description',
            'code',
            'discount_type',
            'discount_value',
            'max_discount_amount',
            'minimum_order_amount',
            'applies_to',
            'applicable_categories',
            'categoryNames',
            'applicable_dishes',
            'dishNames',
            'applicable_dining_types',
            'buy_dish',
            'buyDishName',
            'buy_quantity',
            'get_dish',
            'getDishName',
            'get_quantity',
            'get_discount_percentage',
            'start_date',
            'end_date',
            'has_time_window',
            'start_time',
            'end_time',
            'days_of_week',
            'usage_limit_total',
            'usage_limit_per_customer',
            'times_used',
            'totalDiscountGiven',
            'is_first_order_only',
            'is_active',
            'is_featured',
            'banner_message',
            'isExpired',
            'isStarted',
            'isLimitReached',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'times_used', 'created_at', 'updated_at']

    def get_totalDiscountGiven(self, obj) -> Decimal:
        return sum((u.discount_applied for u in obj.usages.all()), Decimal('0.00'))

    def get_categoryNames(self, obj) -> list:
        return list(obj.applicable_categories.values_list('name', flat=True))

    def get_dishNames(self, obj) -> list:
        return list(obj.applicable_dishes.values_list('name', flat=True))

    def validate(self, data):
        start = data.get('start_date')
        end = data.get('end_date')
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "End date cannot be earlier than start date."})

        disc_type = data.get('discount_type', getattr(self.instance, 'discount_type', None))
        val = data.get('discount_value', getattr(self.instance, 'discount_value', Decimal('0.00')))

        if disc_type == Promotion.DiscountType.PERCENTAGE:
            if val < 0 or val > 100:
                raise serializers.ValidationError({"discount_value": "Percentage discount must be between 0 and 100."})

        return data


class PromotionPublicSerializer(serializers.ModelSerializer):
    """
    Public customer-facing serializer displaying active promos, banners, and discounts.
    """
    discountTypeDisplay = serializers.CharField(source='get_discount_type_display', read_only=True)

    class Meta:
        model = Promotion
        fields = [
            'id',
            'name',
            'description',
            'code',
            'discount_type',
            'discountTypeDisplay',
            'discount_value',
            'minimum_order_amount',
            'banner_message',
            'is_featured',
            'end_date',
        ]


class ValidatePromoCodeRequestSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50, required=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    delivery_fee = serializers.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), required=False)
    dining_type = serializers.CharField(default='delivery', required=False)
    customer_phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default='')
    customer_email = serializers.EmailField(required=False, allow_blank=True, default='')
    items = serializers.ListField(child=serializers.DictField(), required=False, default=list)


class ValidatePromoCodeResponseSerializer(serializers.Serializer):
    isValid = serializers.BooleanField()
    code = serializers.CharField(allow_null=True)
    promotionId = serializers.CharField(allow_null=True)
    promotionName = serializers.CharField(allow_null=True)
    discountType = serializers.CharField(allow_null=True)
    discountAmount = serializers.DecimalField(max_digits=10, decimal_places=2)
    newDeliveryFee = serializers.DecimalField(max_digits=10, decimal_places=2)
    originalSubtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    discountedSubtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    estimatedTotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    message = serializers.CharField()


class PromotionUsageSerializer(serializers.ModelSerializer):
    promotionName = serializers.CharField(source='promotion.name', read_only=True)
    promoCode = serializers.CharField(source='promotion.code', read_only=True, default=None)
    orderNumber = serializers.CharField(source='order.order_number', read_only=True, default=None)
    userName = serializers.SerializerMethodField()

    class Meta:
        model = PromotionUsage
        fields = [
            'id',
            'promotion',
            'promotionName',
            'promoCode',
            'order',
            'orderNumber',
            'user',
            'userName',
            'customer_phone',
            'customer_email',
            'discount_applied',
            'created_at',
        ]

    def get_userName(self, obj) -> str:
        if obj.user:
            return obj.user.get_full_name() or obj.user.username
        return 'Guest'

