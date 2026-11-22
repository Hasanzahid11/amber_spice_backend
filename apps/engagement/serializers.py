from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers
from .models import Promotion, Faq, GalleryItem, Review, ContactMessage, NewsletterSubscriber, RestaurantProfile, BannerSlide


class PostcodePrefixesField(serializers.CharField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        return [part.strip().upper().replace(' ', '') for part in value.split(',') if part.strip()]

    def to_representation(self, value):
        return ', '.join(value or [])


class RestaurantProfileSerializer(serializers.ModelSerializer):
    delivery_postcode_prefixes = PostcodePrefixesField(required=False, allow_blank=True)
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7, min_value=-90, max_value=90, allow_null=True, required=False)
    longitude = serializers.DecimalField(max_digits=11, decimal_places=7, min_value=-180, max_value=180, allow_null=True, required=False)
    delivery_fee = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=0)
    free_delivery_threshold = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    included_vat_percent = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)

    class Meta:
        model = RestaurantProfile
        fields = ['id', 'name', 'story', 'phone', 'email', 'address', 'city', 'opening_hours', 'latitude', 'longitude', 'delivery_postcode_prefixes', 'delivery_fee', 'free_delivery_threshold', 'included_vat_percent', 'ordering_enabled']


class PromotionSerializer(serializers.ModelSerializer):
    discountType = serializers.ChoiceField(source='discount_type', choices=['percentage', 'fixed'])
    discountValue = serializers.DecimalField(source='discount_value', max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    minSpend = serializers.DecimalField(source='min_spend', max_digits=10, decimal_places=2, min_value=Decimal('0'), default=0)
    validUntil = serializers.DateField(source='valid_until')
    usageLimit = serializers.IntegerField(source='usage_limit', min_value=1, default=100)
    usageCount = serializers.IntegerField(source='usage_count', read_only=True)
    isActive = serializers.BooleanField(source='is_active', default=True)
    firstOrderOnly = serializers.BooleanField(source='first_order_only', default=False)
    image = serializers.ImageField(required=False, allow_null=True, write_only=True)
    imageUrl = serializers.CharField(source='image_url', required=False, allow_blank=True)

    class Meta:
        model = Promotion
        fields = ['id', 'code', 'title', 'description', 'discountType', 'discountValue', 'minSpend', 'validUntil', 'usageLimit', 'usageCount', 'isActive', 'firstOrderOnly', 'image', 'imageUrl', 'badge']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.image:
            try:
                request = self.context.get('request')
                if request:
                    data['imageUrl'] = request.build_absolute_uri(instance.image.url)
                else:
                    data['imageUrl'] = f"https://spiceadmin.innovationark.co{instance.image.url}"
            except Exception:
                data['imageUrl'] = f"https://spiceadmin.innovationark.co{instance.image.url}"
        else:
            data['imageUrl'] = instance.image_url or ''
        return data

    def validate_code(self, value):
        value = value.strip().upper()
        if Promotion.objects.filter(code__iexact=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError('This voucher code already exists.')
        return value

    def validate(self, attrs):
        kind = attrs.get('discount_type', self.instance.discount_type if self.instance else None)
        amount = attrs.get('discount_value', self.instance.discount_value if self.instance else 0)
        if kind == 'percentage' and amount > 100:
            raise serializers.ValidationError({'discountValue': 'A percentage cannot exceed 100.'})
        return attrs


class FaqSerializer(serializers.ModelSerializer):
    class Meta:
        model = Faq
        fields = ['id', 'question', 'answer', 'category', 'is_active', 'display_order']


class GalleryItemSerializer(serializers.ModelSerializer):
    imageUrl = serializers.URLField(source='image_url')
    dishId = serializers.IntegerField(source='dish_id', read_only=True, allow_null=True)

    class Meta:
        model = GalleryItem
        fields = ['id', 'title', 'tag', 'description', 'category', 'imageUrl', 'dish', 'dishId', 'is_active']


class ReviewSerializer(serializers.ModelSerializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    helpfulCount = serializers.SerializerMethodField()
    verified = serializers.SerializerMethodField()
    date = serializers.DateTimeField(source='created_at', read_only=True)
    adminReply = serializers.CharField(source='admin_reply', read_only=True)
    repliedAt = serializers.DateTimeField(source='replied_at', read_only=True)

    class Meta:
        model = Review
        fields = [
            'id',
            'order',
            'name',
            'location',
            'rating',
            'dish',
            'comment',
            'helpfulCount',
            'verified',
            'date',
            'is_approved',
            'adminReply',
            'repliedAt',
        ]
        read_only_fields = ['name', 'is_approved', 'adminReply', 'repliedAt']

    def get_helpfulCount(self, obj) -> int:
        return obj.helpful_votes.count()

    def get_verified(self, obj) -> bool:
        return bool(obj.order and obj.order.customer_id == obj.user_id and obj.order.status == 'delivered')

    def validate_order(self, order):
        if order and (order.customer_id != self.context['request'].user.id or order.status != 'delivered'):
            raise serializers.ValidationError('Select your own delivered order.')
        return order


class ReviewModerationSerializer(serializers.ModelSerializer):
    adminReply = serializers.CharField(source='admin_reply', required=False, allow_blank=True)

    class Meta:
        model = Review
        fields = ['is_approved', 'admin_reply', 'adminReply']

    def update(self, instance, validated_data):
        from django.utils import timezone
        if 'admin_reply' in validated_data and validated_data['admin_reply'] != instance.admin_reply:
            validated_data['replied_at'] = timezone.now() if validated_data['admin_reply'].strip() else None
        return super().update(instance, validated_data)


class ContactMessageSerializer(serializers.ModelSerializer):
    fullName = serializers.CharField(source='full_name', max_length=150)
    message = serializers.CharField(max_length=10000)

    class Meta:
        model = ContactMessage
        fields = ['id', 'fullName', 'email', 'subject', 'message', 'status', 'created_at']
        read_only_fields = ['status', 'created_at']


class ContactStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['status']


class NewsletterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    consent = serializers.BooleanField()

    class Meta:
        model = NewsletterSubscriber
        fields = ['id', 'email', 'consent', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_consent(self, value):
        if not value:
            raise serializers.ValidationError('Consent is required to subscribe.')
        return value

    def create(self, validated_data):
        subscriber, _ = NewsletterSubscriber.objects.update_or_create(email=validated_data['email'].lower(), defaults={'consent': True})
        return subscriber


class BannerSlideSerializer(serializers.ModelSerializer):
    titleLine1 = serializers.CharField(source='title_line1', max_length=150)
    titleLine2 = serializers.CharField(source='title_line2', max_length=150, required=False, allow_blank=True)
    ctaText = serializers.CharField(source='cta_text', max_length=80)
    ctaLink = serializers.CharField(source='cta_link', max_length=100, required=False, allow_blank=True)
    imageUrl = serializers.CharField(source='image_url', max_length=500)
    displayOrder = serializers.IntegerField(source='display_order', default=1, min_value=0)
    isActive = serializers.BooleanField(source='is_active', default=True)

    class Meta:
        model = BannerSlide
        fields = [
            'id', 'tag', 'titleLine1', 'titleLine2', 'subtitle',
            'ctaText', 'ctaLink', 'imageUrl', 'displayOrder', 'isActive'
        ]

    def to_internal_value(self, data):
        normalized = dict(data)
        if 'title_line1' in normalized and 'titleLine1' not in normalized:
            normalized['titleLine1'] = normalized['title_line1']
        if 'title_line2' in normalized and 'titleLine2' not in normalized:
            normalized['titleLine2'] = normalized['title_line2']
        if 'cta_text' in normalized and 'ctaText' not in normalized:
            normalized['ctaText'] = normalized['cta_text']
        if 'cta_link' in normalized and 'ctaLink' not in normalized:
            normalized['ctaLink'] = normalized['cta_link']
        if 'image_url' in normalized and 'imageUrl' not in normalized:
            normalized['imageUrl'] = normalized['image_url']
        if 'display_order' in normalized and 'displayOrder' not in normalized:
            normalized['displayOrder'] = normalized['display_order']
        if 'is_active' in normalized and 'isActive' not in normalized:
            normalized['isActive'] = normalized['is_active']
        return super().to_internal_value(normalized)

