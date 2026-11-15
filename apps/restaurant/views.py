from datetime import datetime
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsManagerOrAdmin
from .models import (
    RestaurantProfile,
    RestaurantLocation,
    OperatingHour,
    SpecialHolidayClosure,
    DeliveryZone,
)
from .serializers import (
    RestaurantProfileSerializer,
    RestaurantLocationSerializer,
    OperatingHourSerializer,
    SpecialHolidayClosureSerializer,
    DeliveryZoneSerializer,
    DeliveryCheckRequestSerializer,
    RestaurantOverviewSerializer,
)
from .services import (
    get_restaurant_live_status,
    check_delivery_eligibility,
    get_current_local_datetime,
    get_restaurant_tz,
    _get_active_shifts_for_day,
)


class RestaurantProfileView(APIView):
    """
    GET /api/v1/restaurant/profile/
    Public API: returns the global Amber Spice brand profile, contact info, legal registration,
    cuisines, social links, and amenities.

    PATCH / PUT /api/v1/restaurant/profile/
    Admin/Manager API: updates the restaurant brand and business information.
    """
    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [IsManagerOrAdmin()]

    def get(self, request):
        profile = RestaurantProfile.get_solo()
        serializer = RestaurantProfileSerializer(profile)
        return Response(serializer.data)

    def put(self, request):
        profile = RestaurantProfile.get_solo()
        serializer = RestaurantProfileSerializer(profile, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request):
        profile = RestaurantProfile.get_solo()
        serializer = RestaurantProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class RestaurantOverviewView(APIView):
    """
    GET /api/v1/restaurant/overview/
    Public composite API returning everything needed to render website navigation,
    header announcement bars, footer NAP, live open/closed indicators, and today's hours.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        profile = RestaurantProfile.get_solo()
        primary_location = RestaurantLocation.objects.filter(is_active=True, is_primary=True).first()
        if not primary_location:
            primary_location = RestaurantLocation.objects.filter(is_active=True).first()

        total_locations = RestaurantLocation.objects.filter(is_active=True).count()
        live_status = get_restaurant_live_status(location=primary_location)

        # Retrieve today's shifts
        now_dt = get_current_local_datetime(profile)
        today_date = now_dt.date()
        weekday = today_date.weekday()
        shifts = _get_active_shifts_for_day(weekday, location=primary_location, service_type="all")
        today_shifts_data = [
            {
                "shift_name": s.shift_name,
                "service_type": s.service_type,
                "opens_at": s.opens_at.strftime("%H:%M"),
                "closes_at": s.closes_at.strftime("%H:%M"),
                "notes": s.notes,
            }
            for s in shifts
        ]

        # Announcements from holiday closures or active notices
        announcements = []
        holiday = SpecialHolidayClosure.objects.filter(date=today_date, is_active=True).first()
        if holiday:
            announcements.append(f"{holiday.name}: {holiday.announcement_message}")

        data = {
            "profile": RestaurantProfileSerializer(profile).data,
            "primary_location": RestaurantLocationSerializer(primary_location).data if primary_location else None,
            "total_locations": total_locations,
            "live_status": live_status,
            "today_shifts": today_shifts_data,
            "announcements": announcements,
        }
        return Response(data)


class RestaurantLiveStatusView(APIView):
    """
    GET /api/v1/restaurant/status/
    Returns live real-time operating status.
    Query parameters:
    - location: UUID or branch code (e.g. 'dublin-central')
    - service: 'all', 'dine_in', 'delivery', 'collection' (default: 'all')
    - datetime: ISO 8601 string to simulate status at a given time (e.g. '2026-11-15T19:30:00Z')
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        location_param = request.query_params.get("location")
        service_param = request.query_params.get("service") or "all"
        dt_param = request.query_params.get("datetime")

        location = None
        if location_param:
            location = RestaurantLocation.objects.filter(
                Q(id=location_param) | Q(code=location_param) | Q(slug=location_param)
            ).first()

        at_dt = None
        if dt_param:
            try:
                at_dt = datetime.fromisoformat(dt_param)
            except ValueError:
                return Response(
                    {"error": "Invalid datetime format. Expected ISO 8601 string."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        status_data = get_restaurant_live_status(
            location=location,
            service_type=service_param,
            at_datetime=at_dt
        )
        return Response(status_data)


class DeliveryCheckView(APIView):
    """
    POST /api/v1/restaurant/check-delivery/
    Public API: checks if an address, coordinates, or postal code is within the delivery zone.
    Request body:
    {
        "latitude": 53.3382,
        "longitude": -6.2546,
        "postal_code": "D02 X224",
        "location_id": "optional-uuid"
    }
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = DeliveryCheckRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = check_delivery_eligibility(
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            postal_code=data.get("postal_code"),
            location_id=data.get("location_id")
        )
        return Response(result)


class RestaurantLocationViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing and viewing physical branches & delivery hubs.
    - Public: list, retrieve, check_delivery, hours, status
    - Admin/Manager: create, update, partial_update, destroy
    """
    queryset = RestaurantLocation.objects.all()
    serializer_class = RestaurantLocationSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve", "check_delivery", "hours", "status"]:
            return [permissions.AllowAny()]
        return [IsManagerOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        # For non-admin, default to active locations only
        if not (self.request.user and self.request.user.is_authenticated and (getattr(self.request.user, 'is_manager', False) or getattr(self.request.user, 'is_owner_or_admin', False))):
            qs = qs.filter(is_active=True)

        is_primary = self.request.query_params.get("is_primary")
        if is_primary is not None:
            qs = qs.filter(is_primary=(is_primary.lower() in ["true", "1"]))

        allows_delivery = self.request.query_params.get("allows_delivery")
        if allows_delivery is not None:
            qs = qs.filter(allows_delivery=(allows_delivery.lower() in ["true", "1"]))

        allows_dine_in = self.request.query_params.get("allows_dine_in")
        if allows_dine_in is not None:
            qs = qs.filter(allows_dine_in=(allows_dine_in.lower() in ["true", "1"]))

        return qs

    @action(detail=False, methods=["post"], permission_classes=[permissions.AllowAny])
    def check_delivery(self, request):
        """
        POST /api/v1/restaurant/locations/check_delivery/
        Checks delivery eligibility across all active locations.
        """
        serializer = DeliveryCheckRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = check_delivery_eligibility(
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            postal_code=data.get("postal_code"),
            location_id=data.get("location_id")
        )
        return Response(result)

    @action(detail=True, methods=["get"], permission_classes=[permissions.AllowAny])
    def hours(self, request, pk=None):
        """
        GET /api/v1/restaurant/locations/{id}/hours/
        Returns weekly operating hours specifically for this branch.
        """
        location = self.get_object()
        hours = OperatingHour.objects.filter(location=location).order_by("day_of_week", "opens_at")
        serializer = OperatingHourSerializer(hours, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], permission_classes=[permissions.AllowAny])
    def status(self, request, pk=None):
        """
        GET /api/v1/restaurant/locations/{id}/status/
        Returns live operating status for this specific branch.
        """
        location = self.get_object()
        service_param = request.query_params.get("service") or "all"
        status_data = get_restaurant_live_status(location=location, service_type=service_param)
        return Response(status_data)


class DeliveryZoneViewSet(viewsets.ModelViewSet):
    """
    CRUD API for delivery district zones and postal prefix rules.
    """
    queryset = DeliveryZone.objects.all()
    serializer_class = DeliveryZoneSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        return [IsManagerOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        location_id = self.request.query_params.get("location")
        if location_id:
            qs = qs.filter(location_id=location_id)
        return qs


class OperatingHourViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing weekly recurring shifts.
    - Public: list, retrieve, weekly_schedule
    - Admin/Manager: create, update, partial_update, destroy
    """
    queryset = OperatingHour.objects.all()
    serializer_class = OperatingHourSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve", "weekly_schedule"]:
            return [permissions.AllowAny()]
        return [IsManagerOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        day = self.request.query_params.get("day")
        if day is not None:
            qs = qs.filter(day_of_week=day)

        service = self.request.query_params.get("service")
        if service:
            qs = qs.filter(service_type=service)

        location_id = self.request.query_params.get("location")
        if location_id:
            qs = qs.filter(location_id=location_id)

        return qs

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def weekly_schedule(self, request):
        """
        GET /api/v1/restaurant/hours/weekly_schedule/
        Returns complete 7-day schedule grouped by Monday through Sunday.
        """
        location_id = request.query_params.get("location")
        qs = self.get_queryset()
        if location_id:
            qs = qs.filter(location_id=location_id)

        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        schedule = []

        for day_idx in range(7):
            day_shifts = qs.filter(day_of_week=day_idx).order_by("opens_at")
            shift_list = []
            is_closed = True
            for s in day_shifts:
                if not s.is_closed:
                    is_closed = False
                shift_list.append({
                    "id": str(s.id),
                    "shift_name": s.shift_name,
                    "service_type": s.service_type,
                    "service_display": s.get_service_type_display(),
                    "opens_at": s.opens_at.strftime("%H:%M"),
                    "closes_at": s.closes_at.strftime("%H:%M"),
                    "is_closed": s.is_closed,
                    "notes": s.notes,
                })

            schedule.append({
                "day_of_week": day_idx,
                "day_name": day_names[day_idx],
                "is_closed": is_closed if day_shifts.exists() else False,
                "shifts": shift_list,
                "formatted_hours": (
                    "Closed"
                    if is_closed and day_shifts.exists()
                    else ", ".join(f"{s['opens_at']} - {s['closes_at']}" for s in shift_list if not s["is_closed"])
                )
            })

        return Response({"schedule": schedule})


class SpecialHolidayClosureViewSet(viewsets.ModelViewSet):
    """
    API endpoint for holiday schedules, temporary closures, and adjusted special hours.
    - Public: list, retrieve, upcoming
    - Admin/Manager: create, update, partial_update, destroy
    """
    queryset = SpecialHolidayClosure.objects.all()
    serializer_class = SpecialHolidayClosureSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve", "upcoming"]:
            return [permissions.AllowAny()]
        return [IsManagerOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        location_id = self.request.query_params.get("location")
        if location_id:
            qs = qs.filter(location_id=location_id)
        return qs

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def upcoming(self, request):
        """
        GET /api/v1/restaurant/holidays/upcoming/
        Returns upcoming holiday closures from today forward.
        """
        today = timezone.localdate()
        qs = self.get_queryset().filter(date__gte=today, is_active=True).order_by("date")
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

