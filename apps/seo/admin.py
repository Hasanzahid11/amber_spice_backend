from django.contrib import admin
from .models import RestaurantSEOProfile, PageSEOMetadata, MarketingCampaign, OptimizedImageMetadata


@admin.register(RestaurantSEOProfile)
class RestaurantSEOProfileAdmin(admin.ModelAdmin):
    list_display = (
        'restaurant_name',
        'city',
        'country',
        'phone',
        'email',
        'canonical_domain',
        'updated_at',
    )
    fieldsets = (
        ('General Information & NAP', {
            'fields': (
                'restaurant_name',
                'tagline',
                'canonical_domain',
                'street_address',
                'city',
                'region',
                'postal_code',
                'country',
                'phone',
                'email',
            )
        }),
        ('Google Maps & Local SEO', {
            'fields': (
                'latitude',
                'longitude',
                'google_maps_place_id',
                'google_maps_embed_url',
                'google_business_url',
                'price_range',
                'cuisine_types',
                'opening_hours_json',
            )
        }),
        ('Default Metadata & Social Cards', {
            'fields': (
                'meta_title_default',
                'meta_description_default',
                'og_image_url',
                'twitter_handle',
            )
        }),
        ('Marketing & Tracking Pixels', {
            'fields': (
                'ga4_measurement_id',
                'gtm_container_id',
                'meta_pixel_id',
            )
        }),
    )

    def has_add_permission(self, request):
        # Enforce singleton
        return not RestaurantSEOProfile.objects.exists()


@admin.register(PageSEOMetadata)
class PageSEOMetadataAdmin(admin.ModelAdmin):
    list_display = (
        'page_identifier',
        'page_path',
        'meta_title',
        'sitemap_priority',
        'sitemap_changefreq',
        'is_active',
        'updated_at',
    )
    list_filter = ('is_active', 'sitemap_changefreq')
    search_fields = ('page_identifier', 'page_path', 'meta_title', 'meta_description')


@admin.register(MarketingCampaign)
class MarketingCampaignAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'utm_source',
        'utm_medium',
        'utm_campaign',
        'clicks_count',
        'conversions_count',
        'is_active',
        'start_date',
    )
    list_filter = ('utm_source', 'utm_medium', 'is_active', 'start_date')
    search_fields = ('name', 'utm_campaign', 'utm_source')
    readonly_fields = ('clicks_count', 'conversions_count', 'tracking_url', 'created_at', 'updated_at')


@admin.register(OptimizedImageMetadata)
class OptimizedImageMetadataAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'alt_text',
        'width',
        'height',
        'is_lazy',
        'created_at',
    )
    search_fields = ('title', 'alt_text', 'caption')

