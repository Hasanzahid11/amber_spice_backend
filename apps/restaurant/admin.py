from django.contrib import admin
from .models import (
    RestaurantProfile,
    RestaurantLocation,
    OperatingHour,
    SpecialHolidayClosure,
    DeliveryZone,
)


class OperatingHourInline(admin.TabularInline):
    model = OperatingHour
    extra = 0
    fields = ("day_of_week", "shift_name", "service_type", "opens_at", "closes_at", "is_closed", "notes")
    ordering = ("day_of_week", "opens_at")


class DeliveryZoneInline(admin.TabularInline):
    model = DeliveryZone
    extra = 0
    fields = ("zone_name", "postal_prefixes", "delivery_fee", "min_order_amount", "estimated_delivery_minutes", "is_active")


@admin.register(RestaurantProfile)
class RestaurantProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "legal_name", "primary_phone", "primary_email", "currency", "timezone", "updated_at")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Brand & Story", {
            "fields": ("name", "legal_name", "tagline", "description", "short_description", "logo_url", "hero_image_url")
        }),
        ("Contact & Booking", {
            "fields": ("primary_phone", "secondary_phone", "primary_email", "reservation_email", "support_email", "website_url")
        }),
        ("Legal, Financial & Localization", {
            "fields": ("vat_number", "company_registration_number", "currency", "currency_symbol", "timezone", "price_range")
        }),
        ("Cuisine, Amenities & Social Media", {
            "fields": ("cuisines", "features_and_amenities", "social_media")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at")
        }),
    )

    def has_add_permission(self, request):
        # Disallow adding multiple instances if one exists
        if RestaurantProfile.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(RestaurantLocation)
class RestaurantLocationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "city",
        "is_primary",
        "is_active",
        "allows_dine_in",
        "allows_collection",
        "allows_delivery",
        "delivery_radius_km",
        "phone",
    )
    list_filter = ("is_primary", "is_active", "allows_dine_in", "allows_collection", "allows_delivery", "city")
    search_fields = ("name", "code", "address_line_1", "city", "postal_code", "phone", "email")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [OperatingHourInline, DeliveryZoneInline]

    fieldsets = (
        ("Branch Identification", {
            "fields": ("id", "name", "code", "slug", "is_primary", "is_active", "manager_name")
        }),
        ("Physical Address & Coordinates", {
            "fields": (
                "address_line_1",
                "address_line_2",
                "city",
                "state_or_county",
                "postal_code",
                "country",
                "latitude",
                "longitude",
            )
        }),
        ("Branch Contact", {
            "fields": ("phone", "email")
        }),
        ("Operations & Capacity", {
            "fields": ("allows_dine_in", "allows_collection", "allows_delivery", "seating_capacity")
        }),
        ("Delivery Settings", {
            "fields": (
                "delivery_radius_km",
                "min_delivery_order",
                "delivery_fee_base",
                "free_delivery_threshold",
                "estimated_delivery_time_min",
                "estimated_delivery_time_max",
                "estimated_pickup_time_min",
                "estimated_pickup_time_max",
            )
        }),
        ("Google Maps Integration", {
            "fields": ("google_place_id", "google_maps_url", "google_maps_embed_url")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at")
        }),
    )


@admin.register(OperatingHour)
class OperatingHourAdmin(admin.ModelAdmin):
    list_display = (
        "day_of_week",
        "shift_name",
        "service_type",
        "location",
        "opens_at",
        "closes_at",
        "is_closed",
    )
    list_filter = ("day_of_week", "service_type", "is_closed", "location")
    search_fields = ("shift_name", "notes")
    ordering = ("day_of_week", "opens_at")


@admin.register(SpecialHolidayClosure)
class SpecialHolidayClosureAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "name",
        "closure_type",
        "service_type",
        "location",
        "opens_at",
        "closes_at",
        "is_active",
    )
    list_filter = ("closure_type", "service_type", "is_active", "date")
    search_fields = ("name", "announcement_message")
    ordering = ("date", "opens_at")


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = (
        "zone_name",
        "location",
        "delivery_fee",
        "min_order_amount",
        "estimated_delivery_minutes",
        "is_active",
    )
    list_filter = ("is_active", "location")
    search_fields = ("zone_name", "postal_prefixes")

