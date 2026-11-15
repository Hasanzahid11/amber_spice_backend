from datetime import datetime, date, time, timedelta
from decimal import Decimal
import zoneinfo
from django.db.models import Q
from django.utils import timezone
from .models import (
    RestaurantProfile,
    RestaurantLocation,
    OperatingHour,
    SpecialHolidayClosure,
    DeliveryZone,
)


def get_restaurant_tz(profile: RestaurantProfile = None):
    """
    Returns zoneinfo timezone object configured in RestaurantProfile.
    Defaults to Europe/Dublin.
    """
    if profile is None:
        profile = RestaurantProfile.get_solo()
    tz_str = profile.timezone or "Europe/Dublin"
    try:
        return zoneinfo.ZoneInfo(tz_str)
    except Exception:
        return zoneinfo.ZoneInfo("Europe/Dublin")


def get_current_local_datetime(profile: RestaurantProfile = None) -> datetime:
    """
    Returns the current datetime localized to the restaurant's timezone.
    """
    tz = get_restaurant_tz(profile)
    return timezone.now().astimezone(tz)


def models_match_location(location):
    if location:
        return Q(location=location) | Q(location__isnull=True)
    return Q(location__isnull=True)


def get_restaurant_live_status(
    location=None,
    service_type: str = "all",
    at_datetime: datetime = None
) -> dict:
    """
    Computes real-time open/closed status for Amber Spice or a specific branch.
    Accounts for:
    - Timezone localization (Europe/Dublin).
    - Special Holiday Closures & Adjusted Hours.
    - Weekly recurring multi-shift schedules (Lunch / Dinner).
    - Service-specific capabilities (Dine-in, Takeaway, Delivery).
    - Closing soon detection (within 30 minutes).
    - Next opening prediction (today or future days).
    """
    profile = RestaurantProfile.get_solo()
    tz = get_restaurant_tz(profile)

    if at_datetime is None:
        now_dt = get_current_local_datetime(profile)
    else:
        if timezone.is_naive(at_datetime):
            now_dt = at_datetime.replace(tzinfo=tz)
        else:
            now_dt = at_datetime.astimezone(tz)

    today_date = now_dt.date()
    current_time = now_dt.time()
    weekday = today_date.weekday()  # 0=Monday .. 6=Sunday

    # Resolve location
    if location is None:
        location = RestaurantLocation.objects.filter(is_active=True, is_primary=True).first()
        if location is None:
            location = RestaurantLocation.objects.filter(is_active=True).first()

    # 1. Check Special Holiday Closures for today
    holiday_filter = models_match_location(location) if location else models_match_location(None)
    holiday = SpecialHolidayClosure.objects.filter(
        date=today_date,
        is_active=True
    ).filter(holiday_filter).first()

    if holiday:
        if holiday.closure_type == SpecialHolidayClosure.ClosureType.CLOSED:
            next_open = _find_next_opening_after(today_date, current_time, location, service_type)
            return {
                "is_open": False,
                "status_code": "CLOSED_HOLIDAY",
                "status_badge": "Holiday Closure",
                "service_type": service_type,
                "current_shift": None,
                "closes_at": None,
                "is_closing_soon": False,
                "minutes_until_close": 0,
                "holiday_name": holiday.name,
                "announcement": holiday.announcement_message,
                "message": f"Closed today for {holiday.name}. {holiday.announcement_message}",
                "next_opening": next_open,
                "current_time_local": now_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "location": {
                    "id": str(location.id) if location else None,
                    "name": location.name if location else profile.name,
                    "phone": location.phone if location else profile.primary_phone,
                } if location else None
            }
        elif holiday.closure_type == SpecialHolidayClosure.ClosureType.SPECIAL_HOURS:
            # Holiday with special hours
            is_special_open = False
            if holiday.opens_at and holiday.closes_at:
                if holiday.opens_at <= holiday.closes_at:
                    is_special_open = holiday.opens_at <= current_time <= holiday.closes_at
                else:
                    is_special_open = current_time >= holiday.opens_at or current_time <= holiday.closes_at

            if is_special_open:
                closes_dt = datetime.combine(today_date, holiday.closes_at)
                if holiday.closes_at < holiday.opens_at and current_time >= holiday.opens_at:
                    closes_dt += timedelta(days=1)
                mins_left = max(0, int((closes_dt - datetime.combine(today_date, current_time)).total_seconds() // 60))
                closing_soon = mins_left <= 30

                return {
                    "is_open": True,
                    "status_code": "CLOSING_SOON" if closing_soon else "OPEN_SPECIAL",
                    "status_badge": "Closing Soon" if closing_soon else "Open (Special Hours)",
                    "service_type": service_type,
                    "current_shift": f"Special Hours ({holiday.name})",
                    "closes_at": holiday.closes_at.strftime("%H:%M"),
                    "is_closing_soon": closing_soon,
                    "minutes_until_close": mins_left,
                    "holiday_name": holiday.name,
                    "announcement": holiday.announcement_message,
                    "message": f"Open today under special hours for {holiday.name} until {holiday.closes_at.strftime('%H:%M')}.",
                    "next_opening": None,
                    "current_time_local": now_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                    "location": {
                        "id": str(location.id) if location else None,
                        "name": location.name if location else profile.name,
                        "phone": location.phone if location else profile.primary_phone,
                    } if location else None
                }
            else:
                next_open = _find_next_opening_after(today_date, current_time, location, service_type)
                return {
                    "is_open": False,
                    "status_code": "CLOSED_SPECIAL_HOURS",
                    "status_badge": "Closed Now",
                    "service_type": service_type,
                    "current_shift": None,
                    "closes_at": None,
                    "is_closing_soon": False,
                    "minutes_until_close": 0,
                    "holiday_name": holiday.name,
                    "announcement": holiday.announcement_message,
                    "message": f"Currently closed. Special holiday hours for {holiday.name} are {holiday.opens_at.strftime('%H:%M')} - {holiday.closes_at.strftime('%H:%M')}.",
                    "next_opening": next_open,
                    "current_time_local": now_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                    "location": {
                        "id": str(location.id) if location else None,
                        "name": location.name if location else profile.name,
                        "phone": location.phone if location else profile.primary_phone,
                    } if location else None
                }

    # 2. Check regular weekly shifts for today
    shifts = _get_active_shifts_for_day(weekday, location, service_type)

    active_shift = None
    for shift in shifts:
        if shift.is_open_at_time(current_time):
            active_shift = shift
            break

    if active_shift:
        # Calculate time remaining until close
        closes_at_time = active_shift.closes_at
        closes_dt = datetime.combine(today_date, closes_at_time)
        if closes_at_time < active_shift.opens_at and current_time >= active_shift.opens_at:
            closes_dt += timedelta(days=1)
        mins_left = max(0, int((closes_dt - datetime.combine(today_date, current_time)).total_seconds() // 60))
        closing_soon = mins_left <= 30

        return {
            "is_open": True,
            "status_code": "CLOSING_SOON" if closing_soon else "OPEN",
            "status_badge": "Closing Soon" if closing_soon else "Open Now",
            "service_type": service_type,
            "current_shift": active_shift.shift_name,
            "closes_at": closes_at_time.strftime("%H:%M"),
            "is_closing_soon": closing_soon,
            "minutes_until_close": mins_left,
            "holiday_name": None,
            "announcement": active_shift.notes or None,
            "message": (
                f"Closing soon at {closes_at_time.strftime('%H:%M')} ({mins_left} mins remaining)"
                if closing_soon
                else f"Open now for {active_shift.shift_name} until {closes_at_time.strftime('%H:%M')}"
            ),
            "next_opening": None,
            "current_time_local": now_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "location": {
                "id": str(location.id) if location else None,
                "name": location.name if location else profile.name,
                "phone": location.phone if location else profile.primary_phone,
            } if location else None
        }

    # If currently closed, find when it opens next
    next_open = _find_next_opening_after(today_date, current_time, location, service_type)
    next_msg = ""
    if next_open:
        if next_open["is_today"]:
            next_msg = f"Opens today at {next_open['opens_at']} for {next_open['shift_name']}."
        else:
            next_msg = f"Opens {next_open['day_name']} at {next_open['opens_at']} for {next_open['shift_name']}."
    else:
        next_msg = "Please check our weekly schedule or call us for opening details."

    return {
        "is_open": False,
        "status_code": "CLOSED",
        "status_badge": "Closed Now",
        "service_type": service_type,
        "current_shift": None,
        "closes_at": None,
        "is_closing_soon": False,
        "minutes_until_close": 0,
        "holiday_name": None,
        "announcement": None,
        "message": f"Currently closed. {next_msg}".strip(),
        "next_opening": next_open,
        "current_time_local": now_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "location": {
            "id": str(location.id) if location else None,
            "name": location.name if location else profile.name,
            "phone": location.phone if location else profile.primary_phone,
        } if location else None
    }


def _get_active_shifts_for_day(weekday: int, location=None, service_type: str = "all"):
    """
    Retrieves active shifts for a given weekday, filtered by location and service.
    """

    qs = OperatingHour.objects.filter(day_of_week=weekday, is_closed=False)

    if location:
        qs = qs.filter(Q(location=location) | Q(location__isnull=True))
    else:
        qs = qs.filter(location__isnull=True)

    if service_type != "all":
        qs = qs.filter(Q(service_type=service_type) | Q(service_type=OperatingHour.ServiceType.ALL))

    return list(qs.order_by("opens_at"))


def _find_next_opening_after(today_date: date, current_time: time, location=None, service_type: str = "all"):
    """
    Finds the earliest upcoming open shift over the next 7 days.
    """
    # First check remaining shifts today
    weekday = today_date.weekday()
    today_shifts = _get_active_shifts_for_day(weekday, location, service_type)
    for shift in today_shifts:
        if shift.opens_at > current_time:
            return {
                "date": today_date.strftime("%Y-%m-%d"),
                "is_today": True,
                "day_name": shift.day_name,
                "opens_at": shift.opens_at.strftime("%H:%M"),
                "closes_at": shift.closes_at.strftime("%H:%M"),
                "shift_name": shift.shift_name,
                "service_type": shift.service_type,
            }

    # Check future days up to 7 days ahead
    for day_offset in range(1, 8):
        future_date = today_date + timedelta(days=day_offset)
        future_weekday = future_date.weekday()

        # Check if holiday closure on future date
        holiday = SpecialHolidayClosure.objects.filter(
            date=future_date,
            is_active=True
        ).filter(models_match_location(location)).first() if location else SpecialHolidayClosure.objects.filter(
            date=future_date,
            is_active=True
        ).first()

        if holiday:
            if holiday.closure_type == SpecialHolidayClosure.ClosureType.CLOSED:
                continue
            elif holiday.closure_type == SpecialHolidayClosure.ClosureType.SPECIAL_HOURS and holiday.opens_at:
                return {
                    "date": future_date.strftime("%Y-%m-%d"),
                    "is_today": False,
                    "day_name": future_date.strftime("%A"),
                    "opens_at": holiday.opens_at.strftime("%H:%M"),
                    "closes_at": holiday.closes_at.strftime("%H:%M") if holiday.closes_at else "",
                    "shift_name": f"Special Hours ({holiday.name})",
                    "service_type": holiday.service_type,
                }

        future_shifts = _get_active_shifts_for_day(future_weekday, location, service_type)
        if future_shifts:
            first_shift = future_shifts[0]
            return {
                "date": future_date.strftime("%Y-%m-%d"),
                "is_today": False,
                "day_name": first_shift.day_name,
                "opens_at": first_shift.opens_at.strftime("%H:%M"),
                "closes_at": first_shift.closes_at.strftime("%H:%M"),
                "shift_name": first_shift.shift_name,
                "service_type": first_shift.service_type,
            }

    return None


def check_delivery_eligibility(
    latitude: float = None,
    longitude: float = None,
    postal_code: str = None,
    location_id=None
) -> dict:
    """
    Checks if a target customer address/coordinate or postal code is eligible for delivery.
    Returns matching branch details, calculated distance, estimated time, and fees.
    """
    locations_qs = RestaurantLocation.objects.filter(is_active=True, allows_delivery=True)

    if location_id:
        locations_qs = locations_qs.filter(id=location_id)

    locations = list(locations_qs)
    if not locations:
        return {
            "is_deliverable": False,
            "message": "Delivery service is currently not active or no delivery branches are available.",
            "location": None,
            "distance_km": None,
            "delivery_fee": None,
            "min_order_amount": None,
            "estimated_delivery_minutes": None,
        }

    # If postal code provided, check DeliveryZone first
    if postal_code:
        for loc in locations:
            matching_zone = loc.delivery_zones.filter(is_active=True)
            for zone in matching_zone:
                if zone.matches_postal_code(postal_code):
                    return {
                        "is_deliverable": True,
                        "matched_by": "postal_zone",
                        "zone_name": zone.zone_name,
                        "message": f"Great news! We deliver to your area from {loc.name}.",
                        "location": {
                            "id": str(loc.id),
                            "name": loc.name,
                            "code": loc.code,
                            "phone": loc.phone,
                        },
                        "distance_km": None,
                        "delivery_fee": float(zone.delivery_fee),
                        "min_order_amount": float(zone.min_order_amount),
                        "free_delivery_threshold": float(loc.free_delivery_threshold),
                        "estimated_delivery_minutes": zone.estimated_delivery_minutes,
                    }

    # If geo coordinates provided, check Haversine distance
    if latitude is not None and longitude is not None:
        best_match = None
        min_distance = float('inf')

        for loc in locations:
            dist = loc.calculate_distance_km(latitude, longitude)
            if dist <= float(loc.delivery_radius_km) and dist < min_distance:
                min_distance = dist
                best_match = loc

        if best_match:
            # Check if there is an active zone for this location
            delivery_fee = float(best_match.delivery_fee_base)
            min_order = float(best_match.min_delivery_order)
            est_mins = best_match.estimated_delivery_time_max

            return {
                "is_deliverable": True,
                "matched_by": "geo_radius",
                "message": f"Great news! We deliver to your location ({min_distance} km from {best_match.name}).",
                "location": {
                    "id": str(best_match.id),
                    "name": best_match.name,
                    "code": best_match.code,
                    "phone": best_match.phone,
                },
                "distance_km": min_distance,
                "delivery_fee": delivery_fee,
                "min_order_amount": min_order,
                "free_delivery_threshold": float(best_match.free_delivery_threshold),
                "estimated_delivery_minutes": est_mins,
            }
        else:
            # Coordinates outside all branches
            return {
                "is_deliverable": False,
                "matched_by": "geo_radius",
                "message": (
                    "We're sorry, your location is outside our direct delivery radius. "
                    "However, you can still place a collection/takeaway order!"
                ),
                "location": None,
                "distance_km": round(min_distance, 2) if min_distance != float('inf') else None,
                "delivery_fee": None,
                "min_order_amount": None,
                "estimated_delivery_minutes": None,
            }

    return {
        "is_deliverable": False,
        "message": "Please provide either coordinates (latitude & longitude) or a postal code / Eircode.",
        "location": None,
        "distance_km": None,
        "delivery_fee": None,
        "min_order_amount": None,
        "estimated_delivery_minutes": None,
    }
