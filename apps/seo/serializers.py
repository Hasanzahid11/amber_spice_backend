from rest_framework import serializers
from .models import RestaurantSEOProfile, PageSEOMetadata, MarketingCampaign, OptimizedImageMetadata


class RestaurantSEOProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantSEOProfile
        fields = '__all__'


class PageSEOMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = PageSEOMetadata
        fields = '__all__'


class MarketingCampaignSerializer(serializers.ModelSerializer):
    trackingUrl = serializers.CharField(source='tracking_url', read_only=True)

    class Meta:
        model = MarketingCampaign
        fields = [
            'id',
            'name',
            'utm_source',
            'utm_medium',
            'utm_campaign',
            'utm_term',
            'utm_content',
            'target_path',
            'trackingUrl',
            'clicks_count',
            'conversions_count',
            'is_active',
            'start_date',
            'end_date',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'clicks_count', 'conversions_count', 'created_at', 'updated_at']


class OptimizedImageMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = OptimizedImageMetadata
        fields = '__all__'


class PageSEOBundleResponseSerializer(serializers.Serializer):
    metaTitle = serializers.CharField()
    metaDescription = serializers.CharField()
    canonicalUrl = serializers.CharField()
    robotsDirective = serializers.CharField()
    openGraph = serializers.DictField()
    twitter = serializers.DictField()
    analytics = serializers.DictField()
    schemaJsonLd = serializers.DictField()


class LocalSEOBundleResponseSerializer(serializers.Serializer):
    restaurantName = serializers.CharField()
    tagline = serializers.CharField()
    nap = serializers.DictField()
    geo = serializers.DictField()
    googleMaps = serializers.DictField()
    openingHours = serializers.DictField()
    priceRange = serializers.CharField()
    cuisines = serializers.ListField()
    schemaJsonLd = serializers.DictField()

