import math
import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone


def get_default_amenities():
    return {
        "halal_certified": True,
        "vegetarian_friendly": True,
        "vegan_options": True,
        "gluten_free_options": True,
        "wheelchair_accessible": True,
        "free_wifi": True,
        "outdoor_seating": True,
        "air_conditioning": True,
        "private_dining": True,
        "parking_available": True,
        "fully_licensed_bar": True,
        "dine_in_available": True,
        "collection_available": True,
        "delivery_available": True,
        "table_booking_available": True,
    }


def get_default_cuisines():
    return [
        "Authentic Indian",
        "Tandoori Grill",
        "Slow-Cooked Curries",
        "Aromatic Biryani",
        "Mughlai Specialities",
        "Street Food & Starters"
    ]


def get_default_socials():
    return {
        "instagram": "https://instagram.com/amberspicedublin",
        "facebook": "https://facebook.com/amberspicedublin",
        "twitter": "https://twitter.com/amberspicedublin",
        "tiktok": "https://tiktok.com/@amberspicedublin",
        "tripadvisor": "https://www.tripadvisor.com/Restaurant_Review-AmberSpice",
        "google_maps": "https://maps.google.com/?cid=123456789",
        "youtube": ""
    }


class RestaurantProfile(models.Model):
    """
    Singleton model representing the core Amber Spice restaurant brand, legal identity,
    contact info, social channels, and hospitality amenities.
    """
    name = models.CharField(
        max_length=200,
        default="Amber Spice Restaurant & Takeaway",
        help_text="Brand name displayed to customers"
    )
    legal_name = models.CharField(
        max_length=200,
        default="Amber Spice Hospitality Ltd.",
        help_text="Registered legal company entity"
    )
    tagline = models.CharField(
        max_length=255,
        default="Authentic Indian Cuisine & Fine Dining in Dublin"
    )
    description = models.TextField(
        default=(
            "Welcome to Amber Spice, Dublin's premier destination for authentic Indian cuisine. "
            "Our passionate culinary team prepares traditional curries, sizzling tandoori delicacies, "
            "and fragrant biryanis using whole roasted spices, fresh Irish meats, and centuries-old culinary craft. "
            "Join us for dine-in, order online for delivery, or book our exclusive private dining suite."
        )
    )
    short_description = models.CharField(
        max_length=300,
        default="Award-winning authentic Indian cuisine, tandoori grills, and curries in Dublin. Dine-in, collection, and delivery available 7 days a week."
    )
    logo_url = models.URLField(
        blank=True,
        default="https://amberspice.ie/assets/logo.png",
        help_text="Primary logo image URL"
    )
    hero_image_url = models.URLField(
        blank=True,
        default="https://amberspice.ie/assets/hero-restaurant.jpg",
        help_text="Hero banner image for website and apps"
    )

    # Primary Contact & Booking Information
    primary_phone = models.CharField(max_length=30, default="+353 (0)1 234 5678")
    secondary_phone = models.CharField(max_length=30, blank=True, default="+353 (0)1 234 5679")
    primary_email = models.EmailField(default="info@amberspice.ie")
    reservation_email = models.EmailField(default="reservations@amberspice.ie")
    support_email = models.EmailField(default="support@amberspice.ie")
    website_url = models.URLField(default="https://amberspice.ie")

    # Legal & Financial
    vat_number = models.CharField(max_length=50, default="IE 9876543A", help_text="VAT / GST registration number")
    company_registration_number = models.CharField(max_length=50, default="CRO 654321", help_text="Company registration number")
    currency = models.CharField(max_length=10, default="EUR")
    currency_symbol = models.CharField(max_length=5, default="€")
    timezone = models.CharField(max_length=50, default="Europe/Dublin")
    price_range = models.CharField(max_length=10, default="€€", help_text="Typical price bracket: €, €€, or €€€")

    # Culinary, Dietary & Amenities
    cuisines = models.JSONField(
        default=get_default_cuisines,
        blank=True,
        help_text="List of culinary styles offered"
    )
    features_and_amenities = models.JSONField(
        default=get_default_amenities,
        blank=True,
        help_text="Dict of hospitality amenities and certifications"
    )
    social_media = models.JSONField(
        default=get_default_socials,
        blank=True,
        help_text="Social media handles and channel URLs"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Restaurant Profile"
        verbose_name_plural = "Restaurant Profile"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Enforce singleton pattern: always keep primary key = 1
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        """
        Retrieves the singleton profile, or creates the default instance if it does not exist yet.
        """
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class RestaurantLocation(models.Model):
    """
    Physical restaurant branches or delivery hub outlets.
    Supports multi-location scaling (Flagship branch, Southside dark kitchen, etc.)
    with geo-coordinates, Haversine delivery radius checking, and operational capabilities.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=200,
        default="Amber Spice Dublin City Centre (Flagship)",
        help_text="Branch name (e.g. Amber Spice Dublin City Centre, Amber Spice Sandyford Hub)"
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        default="dublin-central",
        help_text="Unique branch identifier code (e.g. dublin-central, dublin-south)"
    )
    slug = models.SlugField(max_length=100, unique=True, default="dublin-city-centre")
    is_primary = models.BooleanField(
        default=True,
        help_text="Flagship / primary branch for default public routing"
    )
    is_active = models.BooleanField(default=True, help_text="Whether this branch is active")

    # Address & Location Details
    address_line_1 = models.CharField(max_length=255, default="12 Merrion Row")
    address_line_2 = models.CharField(max_length=255, blank=True, default="St. Stephen's Green")
    city = models.CharField(max_length=100, default="Dublin")
    state_or_county = models.CharField(max_length=100, default="Co. Dublin")
    postal_code = models.CharField(max_length=20, default="D02 X224", help_text="Postal code or Eircode")
    country = models.CharField(max_length=10, default="IE")

    # Geo Coordinates (WGS84)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        default=Decimal('53.338200'),
        help_text="Geographic latitude"
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        default=Decimal('-6.254600'),
        help_text="Geographic longitude"
    )

    # Branch Contact & Staffing
    phone = models.CharField(max_length=30, default="+353 (0)1 234 5678")
    email = models.EmailField(default="dublin@amberspice.ie")
    manager_name = models.CharField(max_length=100, blank=True, default="Rajesh Sharma")

    # Service Capabilities
    allows_dine_in = models.BooleanField(default=True, help_text="Offers table seating & reservations")
    allows_collection = models.BooleanField(default=True, help_text="Offers customer pickup / takeaway")
    allows_delivery = models.BooleanField(default=True, help_text="Offers direct hot food delivery")
    seating_capacity = models.PositiveIntegerField(default=80, help_text="Total seated guest capacity")

    # Delivery Operational Parameters
    delivery_radius_km = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('7.50'),
        help_text="Maximum straight-line delivery radius in kilometers"
    )
    min_delivery_order = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('15.00'),
        help_text="Minimum basket total required for delivery"
    )
    delivery_fee_base = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('2.99'),
        help_text="Standard delivery fee"
    )
    free_delivery_threshold = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('40.00'),
        help_text="Spend threshold for free delivery"
    )
    estimated_delivery_time_min = models.PositiveIntegerField(default=30, help_text="Minutes min")
    estimated_delivery_time_max = models.PositiveIntegerField(default=45, help_text="Minutes max")
    estimated_pickup_time_min = models.PositiveIntegerField(default=15, help_text="Minutes min for takeaway")
    estimated_pickup_time_max = models.PositiveIntegerField(default=25, help_text="Minutes max for takeaway")

    # Google Maps Integration
    google_place_id = models.CharField(
        max_length=150,
        blank=True,
        default="ChIJrTLr-GyuEmsRBfy61i59si0",
        help_text="Google Maps Place ID"
    )
    google_maps_url = models.URLField(
        max_length=500,
        blank=True,
        default="https://maps.google.com/?q=Amber+Spice+Dublin",
        help_text="Direct link to Google Maps"
    )
    google_maps_embed_url = models.URLField(
        max_length=500,
        blank=True,
        default="https://www.google.com/maps/embed?pb=amber-spice-dublin",
        help_text="Google Maps iframe embed URL"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_primary", "name"]
        verbose_name = "Restaurant Location"
        verbose_name_plural = "Restaurant Locations"

    def __str__(self):
        primary_badge = " (Primary)" if self.is_primary else ""
        return f"{self.name}{primary_badge}"

    def get_full_address(self) -> str:
        parts = [self.address_line_1, self.address_line_2, self.city, self.state_or_county, self.postal_code, self.country]
        return ", ".join(p for p in parts if p)

    def calculate_distance_km(self, target_lat: float, target_lng: float) -> float:
        """
        Calculates Great Circle Distance between this location and target coordinates
        using the Haversine formula (returns distance in kilometers).
        """
        earth_radius_km = 6371.0

        lat1 = math.radians(float(self.latitude))
        lon1 = math.radians(float(self.longitude))
        lat2 = math.radians(float(target_lat))
        lon2 = math.radians(float(target_lng))

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return round(earth_radius_km * c, 2)

    def is_point_in_delivery_radius(self, target_lat: float, target_lng: float) -> bool:
        """
        Returns True if target coordinate is within the location's delivery radius.
        """
        distance = self.calculate_distance_km(target_lat, target_lng)
        return distance <= float(self.delivery_radius_km)


class DeliveryZone(models.Model):
    """
    Postal code and district delivery zone rules (e.g. Dublin 2, Dublin 4, Dublin 6, Dublin 8).
    Allows fine-grained delivery control, minimum spend, and custom fees per district.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey(
        RestaurantLocation,
        on_delete=models.CASCADE,
        related_name="delivery_zones"
    )
    zone_name = models.CharField(max_length=100, help_text="e.g. Dublin 2 & 4 City Centre Core")
    postal_prefixes = models.JSONField(
        default=list,
        help_text="List of postal prefixes or Eircode routing codes (e.g. ['D02', 'D04', 'D06'])"
    )
    delivery_fee = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('2.99'))
    min_order_amount = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('15.00'))
    estimated_delivery_minutes = models.PositiveIntegerField(default=35)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["zone_name"]
        verbose_name = "Delivery Zone"
        verbose_name_plural = "Delivery Zones"

    def __str__(self):
        return f"{self.zone_name} ({self.location.name})"

    def matches_postal_code(self, postal_code: str) -> bool:
        """
        Case-insensitive match against registered postal codes or prefixes.
        """
        if not postal_code:
            return False
        clean_code = postal_code.strip().upper().replace(" ", "")
        for prefix in self.postal_prefixes:
            clean_prefix = str(prefix).strip().upper().replace(" ", "")
            if clean_code.startswith(clean_prefix):
                return True
        return False


class OperatingHour(models.Model):
    """
    Weekly operating schedule for the restaurant and its branches.
    Supports separate shifts per day (e.g., Lunch 12:00-15:00, Dinner 17:00-23:00)
    and specific service types (All, Dine-In, Delivery, Collection).
    """
    class DayOfWeek(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    class ServiceType(models.TextChoices):
        ALL = "all", "All Services"
        DINE_IN = "dine_in", "Dine-In"
        COLLECTION = "collection", "Takeaway / Collection"
        DELIVERY = "delivery", "Delivery"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey(
        RestaurantLocation,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="operating_hours",
        help_text="Branch location (leave empty if applies to all branches)"
    )
    day_of_week = models.IntegerField(choices=DayOfWeek.choices)
    service_type = models.CharField(
        max_length=20,
        choices=ServiceType.choices,
        default=ServiceType.ALL,
        help_text="Service applicable for this schedule"
    )
    shift_name = models.CharField(
        max_length=50,
        default="Standard Service",
        help_text="e.g. Lunch Service, Dinner Service, All-Day"
    )
    opens_at = models.TimeField(help_text="Opening time (e.g. 12:00)")
    closes_at = models.TimeField(help_text="Closing time (e.g. 23:00 or 00:30)")
    is_closed = models.BooleanField(
        default=False,
        help_text="Check if closed for this day/shift"
    )
    notes = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional customer notice (e.g. Kitchen closes at 22:30)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["day_of_week", "opens_at"]
        verbose_name = "Operating Hour"
        verbose_name_plural = "Operating Hours"

    def __str__(self):
        loc = f"[{self.location.code}] " if self.location else "[Global] "
        day_str = self.get_day_of_week_display()
        if self.is_closed:
            return f"{loc}{day_str} ({self.get_service_type_display()}): Closed"
        return f"{loc}{day_str} ({self.get_service_type_display()} - {self.shift_name}): {self.opens_at.strftime('%H:%M')} - {self.closes_at.strftime('%H:%M')}"

    @property
    def day_name(self) -> str:
        return self.get_day_of_week_display()

    def is_open_at_time(self, check_time) -> bool:
        """
        Determines if a given datetime.time falls within this shift,
        correctly handling overnight shifts where closes_at < opens_at.
        """
        if self.is_closed:
            return False

        if self.opens_at <= self.closes_at:
            return self.opens_at <= check_time <= self.closes_at
        else:
            # Shift crosses midnight (e.g. opens 17:00, closes 01:00)
            return check_time >= self.opens_at or check_time <= self.closes_at


class SpecialHolidayClosure(models.Model):
    """
    Calendar holiday closures, bank holidays, and adjusted special operating hours.
    Overrides standard weekly OperatingHour schedules for specific calendar dates.
    """
    class ClosureType(models.TextChoices):
        CLOSED = "closed", "Full Day Closed"
        SPECIAL_HOURS = "special_hours", "Adjusted Special Hours"

    class ServiceType(models.TextChoices):
        ALL = "all", "All Services"
        DINE_IN = "dine_in", "Dine-In"
        COLLECTION = "collection", "Takeaway / Collection"
        DELIVERY = "delivery", "Delivery"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey(
        RestaurantLocation,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="special_closures",
        help_text="Branch location (leave empty if applies to all branches)"
    )
    date = models.DateField(help_text="Calendar date (YYYY-MM-DD)")
    name = models.CharField(
        max_length=150,
        help_text="Holiday or event title (e.g. Christmas Day, St. Patrick's Day, Private Gala)"
    )
    closure_type = models.CharField(
        max_length=20,
        choices=ClosureType.choices,
        default=ClosureType.CLOSED
    )
    service_type = models.CharField(
        max_length=20,
        choices=ServiceType.choices,
        default=ServiceType.ALL
    )
    opens_at = models.TimeField(
        null=True,
        blank=True,
        help_text="Opening time if special hours"
    )
    closes_at = models.TimeField(
        null=True,
        blank=True,
        help_text="Closing time if special hours"
    )
    announcement_message = models.CharField(
        max_length=255,
        default="We are closed today in observance of the holiday. Normal hours resume tomorrow.",
        help_text="Customer-facing announcement displayed on banners"
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "opens_at"]
        verbose_name = "Special Holiday Closure"
        verbose_name_plural = "Special Holiday Closures"

    def __str__(self):
        loc = f"[{self.location.code}] " if self.location else "[Global] "
        if self.closure_type == self.ClosureType.CLOSED:
            return f"{loc}{self.date} - {self.name}: Closed"
        opens = self.opens_at.strftime('%H:%M') if self.opens_at else ''
        closes = self.closes_at.strftime('%H:%M') if self.closes_at else ''
        return f"{loc}{self.date} - {self.name}: Special Hours ({opens} - {closes})"

