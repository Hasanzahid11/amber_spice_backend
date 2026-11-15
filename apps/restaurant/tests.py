from datetime import date, time, datetime, timedelta
from decimal import Decimal
import zoneinfo
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import (
    RestaurantProfile,
    RestaurantLocation,
    OperatingHour,
    SpecialHolidayClosure,
    DeliveryZone,
)
from .services import (
    get_restaurant_live_status,
    check_delivery_eligibility,
    get_restaurant_tz,
)

User = get_user_model()


class RestaurantAppTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create Admin User
        self.admin_user = User.objects.create_user(
            email="admin@amberspice.ie",
            phone="+353870000001",
            first_name="Admin",
            last_name="Manager",
            password="StrongPassword123!",
            role=User.Role.ADMIN,
            is_staff=True,
            is_superuser=True
        )

        # Create Normal Customer User
        self.customer_user = User.objects.create_user(
            email="customer@example.com",
            phone="+353870000002",
            first_name="John",
            last_name="Doe",
            password="CustomerPassword123!",
            role=User.Role.CUSTOMER
        )

        # Initialize Default Profile
        self.profile = RestaurantProfile.get_solo()
        self.profile.name = "Amber Spice Restaurant & Takeaway"
        self.profile.timezone = "Europe/Dublin"
        self.profile.save()

        # Create Primary Flagship Location (Dublin 2)
        self.flagship_location = RestaurantLocation.objects.create(
            name="Amber Spice Dublin City Centre (Flagship)",
            code="dublin-central",
            slug="dublin-city-centre",
            is_primary=True,
            is_active=True,
            address_line_1="12 Merrion Row",
            city="Dublin",
            postal_code="D02 X224",
            country="IE",
            latitude=Decimal("53.338200"),
            longitude=Decimal("-6.254600"),
            phone="+353 1 234 5678",
            delivery_radius_km=Decimal("7.50"),
            min_delivery_order=Decimal("15.00"),
            delivery_fee_base=Decimal("2.99"),
            free_delivery_threshold=Decimal("40.00"),
            allows_dine_in=True,
            allows_collection=True,
            allows_delivery=True
        )

        # Create Delivery Zone for Dublin 2 & 4
        self.zone_d2_d4 = DeliveryZone.objects.create(
            location=self.flagship_location,
            zone_name="Dublin 2 & 4 Inner Core",
            postal_prefixes=["D02", "D04"],
            delivery_fee=Decimal("2.50"),
            min_order_amount=Decimal("15.00"),
            estimated_delivery_minutes=30,
            is_active=True
        )

    def test_restaurant_profile_singleton(self):
        """Verify singleton behavior and default values of RestaurantProfile."""
        profile1 = RestaurantProfile.get_solo()
        profile2 = RestaurantProfile.get_solo()
        self.assertEqual(profile1.pk, 1)
        self.assertEqual(profile2.pk, 1)
        self.assertEqual(profile1.currency, "EUR")
        self.assertIn("halal_certified", profile1.features_and_amenities)

    def test_public_get_profile(self):
        """Public users can view restaurant brand profile without auth."""
        url = reverse("restaurant-profile")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Amber Spice Restaurant & Takeaway")
        self.assertEqual(response.data["vat_number"], "IE 9876543A")

    def test_admin_update_profile(self):
        """Admin can update profile, customer receives 403 Forbidden."""
        url = reverse("restaurant-profile")

        # Customer attempts update -> Forbidden
        self.client.force_authenticate(user=self.customer_user)
        patch_res = self.client.patch(url, {"tagline": "Customer Tagline Hack"}, format="json")
        self.assertEqual(patch_res.status_code, status.HTTP_403_FORBIDDEN)

        # Admin updates successfully
        self.client.force_authenticate(user=self.admin_user)
        admin_res = self.client.patch(url, {"tagline": "Finest Michelin-recommended Indian in Dublin"}, format="json")
        self.assertEqual(admin_res.status_code, status.HTTP_200_OK)
        self.assertEqual(admin_res.data["tagline"], "Finest Michelin-recommended Indian in Dublin")

    def test_haversine_distance_and_delivery_radius(self):
        """Test accurate geodesic Haversine distance computation."""
        # Point near Trinity College (~1.0 km away from Merrion Row)
        trinity_lat = 53.3444
        trinity_lng = -6.2592
        dist_km = self.flagship_location.calculate_distance_km(trinity_lat, trinity_lng)
        self.assertLess(dist_km, 2.0)
        self.assertTrue(self.flagship_location.is_point_in_delivery_radius(trinity_lat, trinity_lng))

        # Far point in Galway (~185 km away)
        galway_lat = 53.2707
        galway_lng = -9.0568
        far_dist = self.flagship_location.calculate_distance_km(galway_lat, galway_lng)
        self.assertGreater(far_dist, 100.0)
        self.assertFalse(self.flagship_location.is_point_in_delivery_radius(galway_lat, galway_lng))

    def test_delivery_eligibility_by_coordinates(self):
        """Test POST /api/v1/restaurant/check-delivery/ with coordinates."""
        url = reverse("restaurant-check-delivery")

        # 1. Nearby coordinate in Dublin (Stephen's Green area)
        res_near = self.client.post(url, {
            "latitude": 53.3385,
            "longitude": -6.2550
        }, format="json")
        self.assertEqual(res_near.status_code, status.HTTP_200_OK)
        self.assertTrue(res_near.data["is_deliverable"])
        self.assertEqual(res_near.data["matched_by"], "geo_radius")
        self.assertIsNotNone(res_near.data["distance_km"])
        self.assertEqual(res_near.data["delivery_fee"], 2.99)

        # 2. Distant coordinate (Cork)
        res_far = self.client.post(url, {
            "latitude": 51.8985,
            "longitude": -8.4756
        }, format="json")
        self.assertEqual(res_far.status_code, status.HTTP_200_OK)
        self.assertFalse(res_far.data["is_deliverable"])

    def test_delivery_eligibility_by_postal_code(self):
        """Test POST /api/v1/restaurant/check-delivery/ matching postal zone."""
        url = reverse("restaurant-check-delivery")

        # Matching prefix D02
        res_valid = self.client.post(url, {"postal_code": "D02 X224"}, format="json")
        self.assertEqual(res_valid.status_code, status.HTTP_200_OK)
        self.assertTrue(res_valid.data["is_deliverable"])
        self.assertEqual(res_valid.data["matched_by"], "postal_zone")
        self.assertEqual(res_valid.data["zone_name"], "Dublin 2 & 4 Inner Core")
        self.assertEqual(res_valid.data["delivery_fee"], 2.50)

    def test_operating_hours_weekly_shifts(self):
        """Test operating shifts and live status calculation."""
        tz = zoneinfo.ZoneInfo("Europe/Dublin")
        # Ensure a known weekday for testing: say Wednesday (day 2)
        test_wednesday = date(2026, 11, 18)  # 2026-11-18 is Wednesday (weekday 2)
        self.assertEqual(test_wednesday.weekday(), 2)

        # Create Lunch and Dinner shifts for Wednesday
        OperatingHour.objects.create(
            location=self.flagship_location,
            day_of_week=2,
            service_type=OperatingHour.ServiceType.ALL,
            shift_name="Lunch Service",
            opens_at=time(12, 0),
            closes_at=time(15, 0),
            is_closed=False
        )
        OperatingHour.objects.create(
            location=self.flagship_location,
            day_of_week=2,
            service_type=OperatingHour.ServiceType.ALL,
            shift_name="Dinner Service",
            opens_at=time(17, 0),
            closes_at=time(23, 0),
            is_closed=False
        )

        # Case 1: Open during lunch (13:30)
        dt_lunch = datetime(2026, 11, 18, 13, 30, tzinfo=tz)
        status_lunch = get_restaurant_live_status(
            location=self.flagship_location,
            at_datetime=dt_lunch
        )
        self.assertTrue(status_lunch["is_open"])
        self.assertEqual(status_lunch["current_shift"], "Lunch Service")
        self.assertEqual(status_lunch["closes_at"], "15:00")
        self.assertFalse(status_lunch["is_closing_soon"])

        # Case 2: Closing soon (14:45, 15 mins left)
        dt_closing_soon = datetime(2026, 11, 18, 14, 45, tzinfo=tz)
        status_cs = get_restaurant_live_status(
            location=self.flagship_location,
            at_datetime=dt_closing_soon
        )
        self.assertTrue(status_cs["is_open"])
        self.assertTrue(status_cs["is_closing_soon"])
        self.assertEqual(status_cs["status_badge"], "Closing Soon")
        self.assertEqual(status_cs["minutes_until_close"], 15)

        # Case 3: Closed between lunch and dinner (16:00)
        dt_between = datetime(2026, 11, 18, 16, 0, tzinfo=tz)
        status_between = get_restaurant_live_status(
            location=self.flagship_location,
            at_datetime=dt_between
        )
        self.assertFalse(status_between["is_open"])
        self.assertIsNotNone(status_between["next_opening"])
        self.assertEqual(status_between["next_opening"]["opens_at"], "17:00")
        self.assertEqual(status_between["next_opening"]["shift_name"], "Dinner Service")

        # Case 4: Open during dinner (20:00)
        dt_dinner = datetime(2026, 11, 18, 20, 0, tzinfo=tz)
        status_dinner = get_restaurant_live_status(
            location=self.flagship_location,
            at_datetime=dt_dinner
        )
        self.assertTrue(status_dinner["is_open"])
        self.assertEqual(status_dinner["current_shift"], "Dinner Service")
        self.assertEqual(status_dinner["closes_at"], "23:00")

    def test_special_holiday_closure_override(self):
        """Holiday full closure overrides normal weekly schedule."""
        tz = zoneinfo.ZoneInfo("Europe/Dublin")
        christmas_day = date(2026, 12, 25)

        # Standard schedule says Friday is open
        OperatingHour.objects.create(
            location=self.flagship_location,
            day_of_week=4,  # Friday
            service_type=OperatingHour.ServiceType.ALL,
            shift_name="All Day",
            opens_at=time(12, 0),
            closes_at=time(23, 0),
            is_closed=False
        )

        # Create holiday closure for Christmas Day
        SpecialHolidayClosure.objects.create(
            location=self.flagship_location,
            date=christmas_day,
            name="Christmas Day",
            closure_type=SpecialHolidayClosure.ClosureType.CLOSED,
            announcement_message="Merry Christmas! We are closed to spend time with family."
        )

        dt_xmas_noon = datetime(2026, 12, 25, 13, 0, tzinfo=tz)
        status_xmas = get_restaurant_live_status(
            location=self.flagship_location,
            at_datetime=dt_xmas_noon
        )
        self.assertFalse(status_xmas["is_open"])
        self.assertEqual(status_xmas["status_code"], "CLOSED_HOLIDAY")
        self.assertEqual(status_xmas["holiday_name"], "Christmas Day")
        self.assertIn("Merry Christmas", status_xmas["announcement"])

    def test_restaurant_overview_endpoint(self):
        """Test GET /api/v1/restaurant/overview/ composite endpoint."""
        url = reverse("restaurant-overview")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("profile", response.data)
        self.assertIn("primary_location", response.data)
        self.assertIn("live_status", response.data)
        self.assertIn("today_shifts", response.data)
        self.assertEqual(response.data["primary_location"]["code"], "dublin-central")

    def test_locations_viewset_crud(self):
        """Test location listing and admin creation."""
        url = reverse("restaurant-location-list")

        # Public list
        list_res = self.client.get(url)
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(list_res.data), 1)

        # Admin creates secondary branch (Southside delivery kitchen)
        self.client.force_authenticate(user=self.admin_user)
        create_res = self.client.post(url, {
            "name": "Amber Spice Southside Express & Delivery Hub",
            "code": "dublin-southside",
            "slug": "dublin-southside-express",
            "is_primary": False,
            "is_active": True,
            "address_line_1": "Unit 4 Sandyford Business Park",
            "city": "Dublin",
            "postal_code": "D18 X5R8",
            "country": "IE",
            "latitude": "53.277500",
            "longitude": "-6.216500",
            "phone": "+353 1 234 9999",
            "delivery_radius_km": "8.00",
            "min_delivery_order": "18.00",
            "delivery_fee_base": "3.50",
            "free_delivery_threshold": "45.00",
            "allows_dine_in": False,
            "allows_collection": True,
            "allows_delivery": True
        }, format="json")
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_res.data["code"], "dublin-southside")
        self.assertFalse(create_res.data["allows_dine_in"])
