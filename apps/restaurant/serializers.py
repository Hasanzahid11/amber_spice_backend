from decimal import Decimal
from rest_framework import serializers
from .models import (
    RestaurantProfile,
    RestaurantLocation,
    OperatingHour,
    SpecialHolidayClosure,
    DeliveryZone,
)
from .services import get_restaurant_live_status, check_delivery_eligibility, get_current_local_datetime


class RestaurantProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for the global Amber Spice Restaurant Profile (brand, contact, legal, amenities).
    """
    class Meta:
        model = RestaurantProfile
        fields = [
            "id",
            "name",
            "legal_name",
            "tagline",
            "description",
            "short_description",
            "logo_url",
            "hero_image_url",
            "primary_phone",
            "secondary_phone",
            "primary_email",
            "reservation_email",
            "support_email",
            "website_url",
            "vat_number",
            "company_registration_number",
            "currency",
            "currency_symbol",
            "timezone",
            "price_range",
            "cuisines",
            "features_and_amenities",
            "social_media",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class DeliveryZoneSerializer(serializers.ModelSerializer):
    """
    Serializer for postal/district delivery rules.
    """
    class Meta:
        model = DeliveryZone
        fields = [
            "id",
            "location",
            "zone_name",
            "postal_prefixes",
            "delivery_fee",
            "min_order_amount",
            "estimated_delivery_minutes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class OperatingHourSerializer(serializers.ModelSerializer):
    """
    Serializer for regular weekly shift schedules.
    """
    day_name = serializers.CharField(source="get_day_of_week_display", read_only=True)
    service_type_display = serializers.CharField(source="get_service_type_display", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True, default="All Branches")

    class Meta:
        model = OperatingHour
        fields = [
            "id",
            "location",
            "location_name",
            "day_of_week",
            "day_name",
            "service_type",
            "service_type_display",
            "shift_name",
            "opens_at",
            "closes_at",
            "is_closed",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "day_name", "service_type_display", "location_name"]


class SpecialHolidayClosureSerializer(serializers.ModelSerializer):
    """
    Serializer for holiday closures and special operating hours.
    """
    closure_type_display = serializers.CharField(source="get_closure_type_display", read_only=True)
    service_type_display = serializers.CharField(source="get_service_type_display", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True, default="All Branches")

    class Meta:
        model = SpecialHolidayClosure
        fields = [
            "id",
            "location",
            "location_name",
            "date",
            "name",
            "closure_type",
            "closure_type_display",
            "service_type",
            "service_type_display",
            "opens_at",
            "closes_at",
            "announcement_message",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "closure_type_display", "service_type_display", "location_name"]


class RestaurantLocationSerializer(serializers.ModelSerializer):
    """
    Serializer for physical restaurant branches & delivery kitchen hubs.
    """
    full_address = serializers.CharField(source="get_full_address", read_only=True)
    delivery_zones = DeliveryZoneSerializer(many=True, read_only=True)
    current_status = serializers.SerializerMethodField()

    class Meta:
        model = RestaurantLocation
        fields = [
            "id",
            "name",
            "code",
            "slug",
            "is_primary",
            "is_active",
            "address_line_1",
            "address_line_2",
            "city",
            "state_or_county",
            "postal_code",
            "country",
            "full_address",
            "latitude",
            "longitude",
            "phone",
            "email",
            "manager_name",
            "allows_dine_in",
            "allows_collection",
            "allows_delivery",
            "seating_capacity",
            "delivery_radius_km",
            "min_delivery_order",
            "delivery_fee_base",
            "free_delivery_threshold",
            "estimated_delivery_time_min",
            "estimated_delivery_time_max",
            "estimated_pickup_time_min",
            "estimated_pickup_time_max",
            "google_place_id",
            "google_maps_url",
            "google_maps_embed_url",
            "delivery_zones",
            "current_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "full_address", "created_at", "updated_at", "current_status"]

    def get_current_status(self, obj):
        # Quick summary of live open/closed status for this location
        try:
            status = get_restaurant_live_status(location=obj)
            return {
                "is_open": status["is_open"],
                "status_badge": status["status_badge"],
                "closes_at": status["closes_at"],
                "message": status["message"]
            }
        except Exception:
            return None


class DeliveryCheckRequestSerializer(serializers.Serializer):
    """
    Request serializer for delivery address / coordinate check.
    """
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)
    postal_code = serializers.CharField(required=False, allow_blank=True, max_length=20)
    location_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        has_coords = attrs.get("latitude") is not None and attrs.get("longitude") is not None
        has_postal = bool(attrs.get("postal_code"))
        if not has_coords and not has_postal:
            raise serializers.ValidationError(
                "You must provide either coordinates ('latitude' & 'longitude') or a 'postal_code'."
            )
        return attrs


class RestaurantOverviewSerializer(serializers.Serializer):
    """
    Comprehensive aggregated summary for frontend headers, navigation, footers, and app home.
    """
    profile = RestaurantProfileSerializer()
    primary_location = RestaurantLocationSerializer(allow_null=True)
    total_locations = serializers.IntegerField()
    live_status = serializers.DictField()
    today_shifts = serializers.ListField(child=serializers.DictField())
    announcements = serializers.ListField(child=serializers.CharField())

