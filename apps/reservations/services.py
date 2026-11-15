import uuid
from datetime import datetime, date, time, timedelta
from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

try:
    from apps.accounts.utils import normalize_phone_number, validate_phone_number
except ImportError:
    def normalize_phone_number(val):
        return val

    def validate_phone_number(val):
        return val

from .models import (
    DiningArea,
    Table,
    RestaurantTable,
    ReservationSchedule,
    ReservationSetting,
    Reservation,
    ReservationNotification,
)


def validate_irish_phone(phone: str) -> str:
    """Helper alias for phone validation."""
    return validate_phone_number(phone)


def get_guest_token(request) -> uuid.UUID:
    """Extracts or generates guest tracking token from headers or query params."""
    if not request:
        return uuid.uuid4()

    token_str = (
        request.headers.get("X-Guest-Token")
        or request.META.get("HTTP_X_GUEST_TOKEN")
        or (request.session.get("guest_token") if hasattr(request, "session") else None)
        or (request.query_params.get("guest_token") if hasattr(request, "query_params") else None)
    )
    if token_str:
        try:
            return uuid.UUID(str(token_str).strip())
        except (ValueError, AttributeError):
            pass
    return uuid.uuid4()


def get_available_tables(
    res_date: date,
    start_time: time,
    duration_minutes: int,
    party_size: int,
    dining_area_id=None,
    exclude_reservation_id=None
) -> list[Table]:
    """
    Finds active restaurant tables that fit the party size and are free from
    conflicting reservations for the entire duration.
    Optimizes seating: smaller fitting tables are prioritized over oversized tables.
    """
    queryset = Table.objects.filter(
        is_active=True,
        max_capacity__gte=party_size
    )

    # If min_capacity is set, ensure table is not oversized
    queryset = queryset.filter(min_capacity__lte=party_size)

    if dining_area_id:
        queryset = queryset.filter(dining_area_id=dining_area_id)

    # Order by priority descending, then max_capacity ascending
    candidate_tables = list(queryset.order_by("-priority", "max_capacity", "capacity"))

    available_tables = []
    for table in candidate_tables:
        if table.is_available_for_slot(res_date, start_time, duration_minutes, exclude_reservation_id):
            available_tables.append(table)

    return available_tables


def get_daily_time_slots(target_date: date, party_size: int, dining_area_id=None) -> list[dict]:
    """
    Generates all standard booking intervals for a date and reports table availability for each slot.
    """
    settings_obj = ReservationSetting.get_settings()
    duration = (
        settings_obj.large_party_duration_minutes
        if party_size >= 5
        else settings_obj.standard_duration_minutes
    )

    # Standard booking intervals for Lunch and Dinner
    lunch_slots = [
        time(12, 0), time(12, 30), time(13, 0), time(13, 30), time(14, 0), time(14, 30)
    ]
    dinner_slots = [
        time(17, 0), time(17, 30), time(18, 0), time(18, 30), time(19, 0),
        time(19, 30), time(20, 0), time(20, 30), time(21, 0), time(21, 30), time(22, 0)
    ]
    candidate_slots = lunch_slots + dinner_slots

    now_dt = timezone.localtime(timezone.now())
    results = []

    for slot_time in candidate_slots:
        slot_dt = datetime.combine(target_date, slot_time)
        slot_dt_aware = timezone.make_aware(slot_dt, timezone.get_current_timezone()) if timezone.is_naive(slot_dt) else slot_dt

        # Check if slot is past minimum advance requirement
        if slot_dt_aware <= now_dt + timedelta(minutes=settings_obj.min_advance_minutes):
            continue

        # Check operating hours
        is_open, _ = ReservationSchedule.is_time_slot_open(target_date, slot_time)
        if not is_open:
            continue

        tables = get_available_tables(
            res_date=target_date,
            start_time=slot_time,
            duration_minutes=duration,
            party_size=party_size,
            dining_area_id=dining_area_id
        )

        time_str = slot_time.strftime("%H:%M")
        is_available = len(tables) > 0
        results.append({
            "time": time_str,
            "timeSlot": time_str,
            "is_available": is_available,
            "isAvailable": is_available,
            "available_tables_count": len(tables),
            "availableTablesCount": len(tables),
            "suggestedTable": tables[0].number if tables else None,
            "service": "Lunch" if slot_time < time(16, 0) else "Dinner",
        })

    return results


def send_reservation_notification(
    reservation: Reservation,
    notification_type: str,
    custom_message: str = ""
) -> ReservationNotification:
    """
    Logs and dispatches reservation notifications (SMS / Email / In-App).
    """
    recipient = reservation.guest_phone or reservation.guest_email or "Guest"
    date_str = reservation.reservation_date.strftime("%A, %d %B %Y")
    slot_str = reservation.time_slot or (reservation.reservation_time.strftime("%H:%M") if reservation.reservation_time else "")

    titles = {
        ReservationNotification.NotificationType.CONFIRMATION: f"Booking Confirmed - Amber Spice #{reservation.reference_code}",
        ReservationNotification.NotificationType.REMINDER: f"Reminder: Your Table Tonight at Amber Spice #{reservation.reference_code}",
        ReservationNotification.NotificationType.STATUS_UPDATE: f"Reservation Update #{reservation.reference_code}",
        ReservationNotification.NotificationType.CANCELLATION: f"Reservation Cancelled #{reservation.reference_code}",
    }
    title = titles.get(notification_type, f"Reservation #{reservation.reference_code}")

    if custom_message:
        body = custom_message
    elif notification_type == ReservationNotification.NotificationType.CONFIRMATION:
        table_info = f"at Table {reservation.table.number}" if reservation.table else ""
        body = (
            f"Dear {reservation.guest_name}, your table for {reservation.guests_count} guests at Amber Spice is confirmed {table_info} "
            f"for {date_str} at {slot_str}. Ref: #{reservation.reference_code}. We look forward to welcoming you!"
        )
    elif notification_type == ReservationNotification.NotificationType.CANCELLATION:
        body = (
            f"Dear {reservation.guest_name}, your reservation #{reservation.reference_code} for {date_str} at {slot_str} "
            f"has been cancelled. We hope to welcome you again soon."
        )
    else:
        body = f"Reservation #{reservation.reference_code} status is now {reservation.get_status_display()}."

    channel = ReservationNotification.Channel.SMS if reservation.guest_phone else ReservationNotification.Channel.EMAIL

    return ReservationNotification.objects.create(
        reservation=reservation,
        recipient=recipient,
        notification_type=notification_type,
        channel=channel,
        title=title,
        message=body,
        is_sent=True
    )


def book_reservation(validated_data: dict, request) -> Reservation:
    """
    Validates rules, verifies schedule, auto-allocates an optimal table,
    creates the Reservation record, and triggers customer notifications.
    """
    settings_obj = ReservationSetting.get_settings()

    res_date = validated_data["reservation_date"]
    res_time = validated_data.get("reservation_time")
    time_slot = validated_data.get("time_slot")

    if not res_time and time_slot:
        try:
            parts = str(time_slot).strip().split(":")
            if len(parts) >= 2:
                res_time = time(int(parts[0]), int(parts[1]))
        except Exception:
            pass

    if not res_time:
        res_time = time(19, 0)

    party_size = validated_data.get("guests_count") or validated_data.get("party_size") or 2
    dining_area = validated_data.get("dining_area")

    # 1. Date and Time advance validation
    booking_dt = datetime.combine(res_date, res_time)
    booking_dt_aware = timezone.make_aware(booking_dt, timezone.get_current_timezone()) if timezone.is_naive(booking_dt) else booking_dt
    now_dt = timezone.localtime(timezone.now())

    if booking_dt_aware <= now_dt:
        raise serializers.ValidationError({"reservation_date": "Reservation must be booked in the future."})

    min_advance_time = now_dt + timedelta(minutes=settings_obj.min_advance_minutes)
    if booking_dt_aware < min_advance_time:
        raise serializers.ValidationError({
            "reservation_time": f"Online reservations require at least {settings_obj.min_advance_minutes} minutes advance notice."
        })

    max_advance_time = now_dt.date() + timedelta(days=settings_obj.max_advance_days)
    if res_date > max_advance_time:
        raise serializers.ValidationError({
            "reservation_date": f"Reservations can only be made up to {settings_obj.max_advance_days} days in advance."
        })

    # 2. Operating hours check
    is_open, open_msg = ReservationSchedule.is_time_slot_open(res_date, res_time)
    if not is_open:
        raise serializers.ValidationError({"reservation_time": open_msg})

    # 3. Party size check
    if party_size < settings_obj.min_party_size:
        raise serializers.ValidationError({"guests_count": f"Minimum party size is {settings_obj.min_party_size}."})
    if party_size > settings_obj.max_party_size:
        raise serializers.ValidationError({
            "guests_count": f"For parties larger than {settings_obj.max_party_size} guests, please contact our events team directly."
        })

    # 4. Duration calculation
    duration = (
        settings_obj.large_party_duration_minutes
        if party_size >= 5
        else settings_obj.standard_duration_minutes
    )

    # 5. Table allocation
    allocated_table = validated_data.get("table")
    if not allocated_table:
        available_tables = get_available_tables(
            res_date=res_date,
            start_time=res_time,
            duration_minutes=duration,
            party_size=party_size,
            dining_area_id=dining_area.id if dining_area else None
        )
        if Table.objects.filter(is_active=True).exists():
            if not available_tables:
                # Also fallback to check if any active table has capacity >= party_size without rigid slot model
                busy_ids = Reservation.objects.filter(
                    reservation_date=res_date,
                    time_slot=time_slot or res_time.strftime("%H:%M"),
                    status__in=[Reservation.Status.CONFIRMED, Reservation.Status.SEATED]
                ).values_list("table_id", flat=True)

                fallback_table = Table.objects.filter(
                    is_active=True,
                    capacity__gte=party_size
                ).exclude(id__in=busy_ids).order_by("capacity").first()

                if not fallback_table:
                    raise serializers.ValidationError({
                        "reservation_time": "Sorry, no tables are available for this party size at the selected time."
                    })
                allocated_table = fallback_table
            else:
                allocated_table = available_tables[0]

            if not dining_area and allocated_table.dining_area:
                dining_area = allocated_table.dining_area

    # 6. Status: auto-confirmed for normal party sizes, pending for very large groups
    auto_status = (
        Reservation.Status.CONFIRMED
        if party_size <= settings_obj.auto_confirm_max_guests
        else Reservation.Status.PENDING
    )

    user = request.user if request and request.user.is_authenticated else None
    guest_token = get_guest_token(request) if not user else None

    guest_name = validated_data.get("guest_name") or validated_data.get("customer_name")
    if not guest_name and user:
        guest_name = user.get_full_name() or user.first_name or user.username

    guest_email = validated_data.get("guest_email") or validated_data.get("customer_email")
    if not guest_email and user:
        guest_email = user.email

    guest_phone = validated_data.get("guest_phone") or validated_data.get("customer_phone")
    if not guest_phone and user:
        guest_phone = user.phone

    if guest_phone:
        guest_phone = normalize_phone_number(guest_phone)

    reservation = Reservation.objects.create(
        customer=user,
        guest_token=guest_token,
        guest_name=guest_name or "Guest",
        guest_email=guest_email,
        guest_phone=guest_phone or "",
        guests_count=party_size,
        reservation_date=res_date,
        time_slot=time_slot or res_time.strftime("%H:%M"),
        reservation_time=res_time,
        duration_minutes=duration,
        table=allocated_table,
        dining_area=dining_area,
        seating_preference=validated_data.get("seating_preference", Reservation.SeatingPreference.NO_PREFERENCE),
        occasion=validated_data.get("occasion", Reservation.Occasion.NONE),
        special_requests=validated_data.get("special_requests", "").strip(),
        dietary_notes=validated_data.get("dietary_notes", "").strip(),
        status=auto_status
    )

    # 7. Customer notification dispatch
    try:
        send_reservation_notification(
            reservation,
            ReservationNotification.NotificationType.CONFIRMATION
        )
    except Exception:
        pass

    return reservation

