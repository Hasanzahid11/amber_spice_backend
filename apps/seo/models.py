import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone


class RestaurantSEOProfile(models.Model):
    """
    Global Restaurant SEO, Structured Data, Local Business, and Google Business Profile configuration.
    Singleton pattern - ensures a unified source of truth for NAP (Name, Address, Phone),
    Schema.org markup, Google Maps coordinates, and marketing analytics tags.
    """
    restaurant_name = models.CharField(max_length=200, default="Amber Spice Restaurant & Takeaway")
    tagline = models.CharField(max_length=255, default="Authentic Indian Cuisine & Fine Dining in Dublin")
    meta_title_default = models.CharField(
        max_length=150,
        default="Amber Spice | Authentic Indian Restaurant & Takeaway in Dublin"
    )
    meta_description_default = models.TextField(
        default="Experience authentic Indian cuisine, slow-cooked curries, tandoori grills, and aromatic biryanis at Amber Spice Dublin. Book your table or order online for delivery."
    )
    canonical_domain = models.URLField(
        default="https://amberspice.ie",
        help_text="Canonical website root URL (e.g. https://amberspice.ie)"
    )

    # NAP (Name, Address, Phone) & Local SEO
    street_address = models.CharField(max_length=255, default="12 Merrion Row")
    city = models.CharField(max_length=100, default="Dublin")
    region = models.CharField(max_length=100, default="Co. Dublin")
    postal_code = models.CharField(max_length=20, default="D02 X224")
    country = models.CharField(max_length=10, default="IE")

    # Geo Coordinates & Google Maps Integration
    latitude = models.DecimalField(max_digits=9, decimal_places=6, default=Decimal('53.338200'))
    longitude = models.DecimalField(max_digits=9, decimal_places=6, default=Decimal('-6.254600'))
    google_maps_place_id = models.CharField(max_length=100, blank=True, help_text="Google Maps Place ID for reviews & CID")
    google_maps_embed_url = models.URLField(max_length=500, blank=True, help_text="Embed iframe URL for Google Maps")
    google_business_url = models.URLField(max_length=500, blank=True, help_text="Direct link to Google Business Profile")

    # Contact & Ordering Info
    phone = models.CharField(max_length=30, default="+353 (0)1 234 5678")
    email = models.EmailField(default="info@amberspice.ie")
    price_range = models.CharField(max_length=10, default="€€", help_text="Schema priceRange: €, €€, or €€€")
    cuisine_types = models.JSONField(
        default=list,
        blank=True,
        help_text="Cuisines served: ['Indian', 'Curry', 'Tandoori', 'Biryani', 'South Asian']"
    )
    opening_hours_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Weekly opening hours schema: {'Mo-Su': '12:00-23:00'}"
    )

    # Social & OpenGraph Sharing
    og_image_url = models.URLField(max_length=500, blank=True, help_text="Default 1200x630 share image for social media")
    twitter_handle = models.CharField(max_length=50, blank=True, default="@AmberSpiceDublin")

    # Marketing Pixels & Tracking
    ga4_measurement_id = models.CharField(max_length=50, blank=True, help_text="Google Analytics 4 Measurement ID (e.g. G-XXXXXXX)")
    gtm_container_id = models.CharField(max_length=50, blank=True, help_text="Google Tag Manager Container ID (e.g. GTM-XXXXXXX)")
    meta_pixel_id = models.CharField(max_length=50, blank=True, help_text="Meta / Facebook Pixel ID")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Restaurant SEO & Local Profile'
        verbose_name_plural = 'Restaurant SEO & Local Profile'

    def __str__(self):
        return f"{self.restaurant_name} ({self.city}, {self.country})"

    @classmethod
    def get_profile(cls):
        obj, _ = cls.objects.get_or_create(
            id=1,
            defaults={
                'restaurant_name': "Amber Spice Restaurant & Takeaway",
                'cuisine_types': ["Indian", "Curry", "Tandoori", "Biryani", "South Asian"],
                'opening_hours_json': {
                    "Monday": "12:00-15:00, 17:00-23:00",
                    "Tuesday": "12:00-15:00, 17:00-23:00",
                    "Wednesday": "12:00-15:00, 17:00-23:00",
                    "Thursday": "12:00-15:00, 17:00-23:00",
                    "Friday": "12:00-15:00, 17:00-23:30",
                    "Saturday": "12:00-23:30",
                    "Sunday": "12:00-22:30"
                }
            }
        )
        return obj


class PageSEOMetadata(models.Model):
    """
    Configurable page-level metadata, clean URL paths, OpenGraph tags, and sitemap settings.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    page_identifier = models.CharField(
        max_length=60,
        unique=True,
        help_text="Key identifier (e.g. 'home', 'menu', 'reservations', 'order', 'about', 'contact', 'offers')"
    )
    page_path = models.CharField(
        max_length=200,
        unique=True,
        help_text="Clean URL path (e.g. '/', '/menu', '/reservations', '/order', '/contact')"
    )
    meta_title = models.CharField(max_length=150, help_text="Target 50-60 characters")
    meta_description = models.TextField(help_text="Target 140-160 characters for search snippet")
    meta_keywords = models.CharField(max_length=255, blank=True)
    canonical_url = models.URLField(max_length=500, blank=True)

    # OpenGraph & Social Cards
    og_title = models.CharField(max_length=150, blank=True)
    og_description = models.TextField(blank=True)
    og_image = models.URLField(max_length=500, blank=True)
    og_type = models.CharField(max_length=50, default="website")
    twitter_card = models.CharField(max_length=30, default="summary_large_image")

    # Search Engine Directives
    robots_directive = models.CharField(
        max_length=50,
        default="index, follow",
        help_text="Robots meta tag (e.g. 'index, follow' or 'noindex, follow')"
    )
    schema_type = models.CharField(max_length=50, default="Restaurant")

    # XML Sitemap Directives
    sitemap_priority = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=Decimal('0.8'),
        help_text="0.1 to 1.0 ranking for search crawlers"
    )
    sitemap_changefreq = models.CharField(
        max_length=20,
        default="weekly",
        choices=[
            ('always', 'Always'),
            ('hourly', 'Hourly'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('yearly', 'Yearly'),
            ('never', 'Never'),
        ]
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['page_path']
        verbose_name = 'Page SEO Metadata'
        verbose_name_plural = 'Page SEO Metadata'

    def __str__(self):
        return f"{self.page_identifier} ({self.page_path}) - {self.meta_title[:40]}"


class MarketingCampaign(models.Model):
    """
    Campaign and UTM attribution tracking for Google Search Ads, Local SEO, and social marketing.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, help_text="Campaign name (e.g. Google Local Search Lunch Special)")
    utm_source = models.CharField(max_length=50, help_text="e.g. google, instagram, facebook, newsletter")
    utm_medium = models.CharField(max_length=50, help_text="e.g. cpc, social, email, organic")
    utm_campaign = models.CharField(max_length=100, help_text="e.g. dublin_indian_takeaway")
    utm_term = models.CharField(max_length=100, blank=True)
    utm_content = models.CharField(max_length=100, blank=True)
    target_path = models.CharField(max_length=200, default="/order")

    clicks_count = models.PositiveIntegerField(default=0)
    conversions_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Marketing Campaign'
        verbose_name_plural = 'Marketing Campaigns'

    def __str__(self):
        return f"{self.name} [{self.utm_source}/{self.utm_medium}]"

    @property
    def tracking_url(self) -> str:
        profile = RestaurantSEOProfile.get_profile()
        base = f"{profile.canonical_domain.rstrip('/')}/{self.target_path.lstrip('/')}"
        params = [
            f"utm_source={self.utm_source}",
            f"utm_medium={self.utm_medium}",
            f"utm_campaign={self.utm_campaign}",
        ]
        if self.utm_term:
            params.append(f"utm_term={self.utm_term}")
        if self.utm_content:
            params.append(f"utm_content={self.utm_content}")
        return f"{base}?{'&'.join(params)}"


class OptimizedImageMetadata(models.Model):
    """
    Image SEO metadata for food photos, menus, and restaurant banners.
    Provides descriptive alt text, titles, lazy-loading hints, and responsive WebP formats.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=150)
    alt_text = models.CharField(max_length=255, help_text="Accessible and descriptive alt text for search crawlers")
    image_url = models.URLField(max_length=500)
    webp_url = models.URLField(max_length=500, blank=True, help_text="Optimized WebP modern format URL")
    width = models.PositiveIntegerField(default=1200)
    height = models.PositiveIntegerField(default=800)
    caption = models.TextField(blank=True)
    is_lazy = models.BooleanField(default=True, help_text="Render with loading='lazy' for fast page speed")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Optimized Image Metadata'
        verbose_name_plural = 'Optimized Image Metadata'

    def __str__(self):
        return f"{self.title} (alt: {self.alt_text[:30]})"

