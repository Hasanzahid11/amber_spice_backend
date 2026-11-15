import uuid
from datetime import datetime, date, time, timedelta
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone


class DiningArea(models.Model):
    """
    Sections of the restaurant (e.g. Main Dining Room, Conservatory / Terrace, Private Dining).
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name = "Dining Area"
        verbose_name_plural = "Dining Areas"

    def __str__(self):
        return self.name


class Table(models.Model):
    """
    Physical restaurant tables with capacity, floor area, shape, and real-time status.
    Maintains full backward compatibility with the legacy Table API while providing
    advanced seating capabilities and slot conflict checks.
    """
    class Status(models.TextChoices):
        AVAILABLE = 'available', 'Available'
        OCCUPIED = 'occupied', 'Occupied'
        RESERVED = 'reserved', 'Reserved'

    class Section(models.TextChoices):
        MAIN_HALL = 'main_hall', 'Main Dining Hall'
        WINDOW = 'window', 'Window Seating'
        PATIO = 'patio', 'Outdoor Patio / Terrace'
        VIP_BOOTH = 'vip_booth', 'VIP Booth'
        BAR = 'bar', 'Bar & Lounge'

    class TableShape(models.TextChoices):
        SQUARE = "SQUARE", "Square Table"
        RECTANGULAR = "RECTANGULAR", "Rectangular Table"
        ROUND = "ROUND", "Round Table"
        BOOTH = "BOOTH", "Cozy Booth"
        HIGH_TOP = "HIGH_TOP", "High Top / Bar Table"

    number = models.CharField(
        max_length=30,
        unique=True,
        help_text="Table identifier (e.g. T-1, T-2, Booth 4)"
    )
    capacity = models.PositiveIntegerField(
        default=4,
        help_text="Primary guest seating capacity"
    )
    dining_area = models.ForeignKey(
        DiningArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tables",
        help_text="Optional linked dining area / room"
    )
    min_capacity = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Minimum party size suitable for this table"
    )
    max_capacity = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(1)],
        help_text="Maximum party size accommodated by this table"
    )
    shape = models.CharField(
        max_length=20,
        choices=TableShape.choices,
        default=TableShape.SQUARE
    )
    section = models.CharField(
        max_length=30,
        choices=Section.choices,
        default=Section.MAIN_HALL,
        blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE
    )
    current_order = models.CharField(max_length=50, blank=True, null=True)
    guest_name = models.CharField(max_length=120, blank=True, null=True)
    time_slot = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Active for bookings (disable for repairs or layout changes)"
    )
    is_combinable = models.BooleanField(
        default=False,
        help_text="Can be combined with adjacent tables for large parties"
    )
    priority = models.PositiveIntegerField(
        default=0,
        help_text="Higher priority tables are assigned first"
    )

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        ordering = ['number']
        verbose_name = "Restaurant Table"
        verbose_name_plural = "Restaurant Tables"

    @property
    def table_number(self) -> str:
        return self.number

    @table_number.setter
    def table_number(self, value: str):
        self.number = value

    def is_available_for_slot(
        self,
        res_date: date,
        start_time: time,
        duration_minutes: int,
        exclude_reservation_id=None
    ) -> bool:
        """
        Checks if this table is free from conflicting reservations during the specified window.
        """
        if not self.is_active:
            return False

        dummy_dt = datetime.combine(res_date, start_time)
        end_dt = dummy_dt + timedelta(minutes=duration_minutes)
        req_start = dummy_dt.time()
        req_end = end_dt.time()

        # Conflicting active statuses
        active_statuses = [
            Reservation.Status.PENDING,
            Reservation.Status.CONFIRMED,
            Reservation.Status.SEATED,
            'pending', 'confirmed', 'seated',
            'PENDING', 'CONFIRMED', 'SEATED'
        ]
        bookings = self.reservations.filter(
            reservation_date=res_date,
            status__in=active_statuses
        )
        if exclude_reservation_id:
            bookings = bookings.exclude(id=exclude_reservation_id)

        for b in bookings:
            b_start = b.reservation_time
            b_end = b.end_time

            # Fallback if reservation_time or end_time is not set on older record
            if not b_start and b.time_slot:
                try:
                    parts = str(b.time_slot).strip().split(':')
                    if len(parts) >= 2:
                        b_start = time(int(parts[0]), int(parts[1]))
                except Exception:
                    pass

            if not b_start:
                continue

            if not b_end:
                b_dummy = datetime.combine(res_date, b_start)
                b_end = (b_dummy + timedelta(minutes=b.duration_minutes or 90)).time()

            # Overlap condition: not (b_end <= req_start or b_start >= req_end)
            if not (b_end <= req_start or b_start >= req_end):
                return False

        return True

    def seat_party(self, guest_name: str, current_order: str = None, time_slot: str = None):
        """Marks table as occupied by a guest."""
        self.status = self.Status.OCCUPIED
        self.guest_name = guest_name
        self.current_order = current_order
        self.time_slot = time_slot
        self.save(update_fields=['status', 'guest_name', 'current_order', 'time_slot'])

    def release(self):
        """Releases table back to available."""
        self.status = self.Status.AVAILABLE
        self.guest_name = None
        self.current_order = None
        self.time_slot = None
        self.save(update_fields=['status', 'guest_name', 'current_order', 'time_slot'])

    def save(self, *args, **kwargs):
        # Keep capacity and max_capacity in sync
        if self.capacity and (not self.max_capacity or self.max_capacity == 4):
            self.max_capacity = self.capacity
        elif self.max_capacity and not self.capacity:
            self.capacity = self.max_capacity

        if self.min_capacity > self.max_capacity:
            self.min_capacity = self.max_capacity

        super().save(*args, **kwargs)

    def __str__(self):
        area_str = f" ({self.dining_area.name})" if self.dining_area else f" ({self.get_section_display()})"
        return f"Table {self.number}{area_str} - {self.capacity} guests - {self.get_status_display()}"


# Alias for code expecting RestaurantTable
RestaurantTable = Table


class ReservationSchedule(models.Model):
    """
    Weekly operating service shifts for reservations (Lunch & Dinner).
    """
    class DayOfWeek(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    day_of_week = models.PositiveSmallIntegerField(
        choices=DayOfWeek.choices,
        unique=True
    )
    # Lunch service
    lunch_start = models.TimeField(default="12:00:00", null=True, blank=True)
    lunch_end = models.TimeField(default="15:00:00", null=True, blank=True)
    # Dinner service
    dinner_start = models.TimeField(default="17:00:00", null=True, blank=True)
    dinner_end = models.TimeField(default="23:00:00", null=True, blank=True)
    is_closed = models.BooleanField(
        default=False,
        help_text="Mark entire day closed for reservations"
    )

    class Meta:
        ordering = ["day_of_week"]
        verbose_name = "Reservation Schedule"
        verbose_name_plural = "Reservation Schedules"

    @classmethod
    def is_time_slot_open(cls, target_date: date, target_time: time) -> tuple[bool, str]:
        """
        Validates whether target date & time fall into an active lunch or dinner shift.
        """
        if not cls.objects.exists():
            # Default open 12:00-15:00 and 17:00-23:00 if no records configured yet
            in_lunch = time(12, 0) <= target_time <= time(14, 30)
            in_dinner = time(17, 0) <= target_time <= time(22, 30)
            if in_lunch or in_dinner:
                return True, "Open"
            return False, "Selected time is outside lunch (12:00-15:00) and dinner (17:00-23:00) hours."

        weekday = target_date.weekday()
        sched = cls.objects.filter(day_of_week=weekday).first()
        if not sched:
            return True, "Open"

        if sched.is_closed:
            return False, f"The restaurant is closed for dining on {sched.get_day_of_week_display()}s."

        in_lunch = False
        if sched.lunch_start and sched.lunch_end:
            in_lunch = sched.lunch_start <= target_time <= sched.lunch_end

        in_dinner = False
        if sched.dinner_start and sched.dinner_end:
            in_dinner = sched.dinner_start <= target_time <= sched.dinner_end

        if in_lunch or in_dinner:
            return True, "Open"

        shifts = []
        if sched.lunch_start and sched.lunch_end:
            shifts.append(f"Lunch {sched.lunch_start.strftime('%H:%M')}-{sched.lunch_end.strftime('%H:%M')}")
        if sched.dinner_start and sched.dinner_end:
            shifts.append(f"Dinner {sched.dinner_start.strftime('%H:%M')}-{sched.dinner_end.strftime('%H:%M')}")
        shift_str = " and ".join(shifts) if shifts else "closed"
        return False, f"Selected time is outside service hours on {sched.get_day_of_week_display()} ({shift_str})."

    def __str__(self):
        if self.is_closed:
            return f"{self.get_day_of_week_display()}: Closed"
        return f"{self.get_day_of_week_display()}: Lunch ({self.lunch_start}-{self.lunch_end}), Dinner ({self.dinner_start}-{self.dinner_end})"


class ReservationSetting(models.Model):
    """
    Global configuration for dining slot durations, advance booking windows, and party limits.
    """
    standard_duration_minutes = models.PositiveIntegerField(
        default=90,
        help_text="Default table sitting duration for 1-4 guests (e.g. 90 minutes)"
    )
    large_party_duration_minutes = models.PositiveIntegerField(
        default=120,
        help_text="Sitting duration for large parties 5+ guests (e.g. 120 minutes)"
    )
    min_party_size = models.PositiveIntegerField(default=1)
    max_party_size = models.PositiveIntegerField(
        default=16,
        help_text="Maximum party size allowed via online booking"
    )
    min_advance_minutes = models.PositiveIntegerField(
        default=30,
        help_text="Minimum advance notice in minutes required to book"
    )
    max_advance_days = models.PositiveIntegerField(
        default=60,
        help_text="How many days in advance guests can book"
    )
    auto_confirm_max_guests = models.PositiveIntegerField(
        default=6,
        help_text="Parties up to this size are confirmed automatically; larger parties require staff review"
    )
    cancellation_deadline_hours = models.PositiveIntegerField(
        default=2,
        help_text="Hours before reservation when free online cancellation is allowed"
    )

    class Meta:
        verbose_name = "Reservation Setting"
        verbose_name_plural = "Reservation Settings"

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj

    def __str__(self):
        return f"Reservation Rules (Slot: {self.standard_duration_minutes}m, Max: {self.max_party_size} guests)"


class Reservation(models.Model):
    """
    Table reservation booking supporting guest checkout, authenticated customer profiles,
    table allocations, dietary preferences, and staff floor management.
    Preserves 100% backward compatibility with existing reference codes, guest contact fields,
    and camelCase/snake_case payload contracts.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Confirmation'
        CONFIRMED = 'confirmed', 'Confirmed'
        SEATED = 'seated', 'Seated / Dining'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
        NO_SHOW = 'no_show', 'No-Show'

    class SeatingPreference(models.TextChoices):
        NO_PREFERENCE = "NO_PREFERENCE", "No Preference"
        WINDOW = "WINDOW", "Window Table"
        BOOTH = "BOOTH", "Cozy Booth"
        TERRACE = "TERRACE", "Conservatory / Garden Terrace"
        QUIET_CORNER = "QUIET_CORNER", "Quiet Corner"
        HIGH_TOP = "HIGH_TOP", "High Top / Bar Area"

    class Occasion(models.TextChoices):
        NONE = "NONE", "Regular Dining"
        BIRTHDAY = "BIRTHDAY", "Birthday Celebration"
        ANNIVERSARY = "ANNIVERSARY", "Anniversary"
        DATE_NIGHT = "DATE_NIGHT", "Date Night"
        BUSINESS = "BUSINESS", "Business Lunch / Dinner"
        FAMILY_GATHERING = "FAMILY_GATHERING", "Family Gathering"
        OTHER = "OTHER", "Other Special Occasion"

    # Core Identifiers
    reference_code = models.CharField(
        max_length=36,
        unique=True,
        blank=True,
        db_index=True,
        help_text="Unique booking reference code (e.g. RES-20261114-AB12CD)"
    )
    guest_token = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Guest token allowing guest users to view or cancel reservation"
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='reservations',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Customer account if logged in, null for guest booking"
    )

    # Guest / Customer Contact Info
    guest_name = models.CharField(max_length=150)
    guest_phone = models.CharField(max_length=30, blank=True)
    guest_email = models.EmailField(blank=True, null=True)

    # Booking Specifications
    guests_count = models.PositiveIntegerField(
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(30)]
    )
    reservation_date = models.DateField(db_index=True)
    time_slot = models.CharField(max_length=50, blank=True)
    reservation_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=90)
    end_time = models.TimeField(null=True, blank=True)

    # Table & Dining Area
    table = models.ForeignKey(
        Table,
        related_name='reservations',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    dining_area = models.ForeignKey(
        DiningArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations"
    )
    seating_preference = models.CharField(
        max_length=30,
        choices=SeatingPreference.choices,
        default=SeatingPreference.NO_PREFERENCE
    )

    # Occasion, Dietary & Special Requests
    occasion = models.CharField(
        max_length=30,
        choices=Occasion.choices,
        default=Occasion.NONE
    )
    special_requests = models.TextField(
        blank=True,
        help_text="e.g. High chair needed, wheelchair access, quiet table"
    )
    dietary_notes = models.TextField(
        blank=True,
        help_text="e.g. 1 vegetarian, 1 nut allergy"
    )

    # Status & Lifecycle Tracking
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CONFIRMED
    )
    cancellation_reason = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    seated_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['reservation_date', 'time_slot']
        verbose_name = "Reservation"
        verbose_name_plural = "Reservations"

    def __init__(self, *args, **kwargs):
        # Map modern kwargs to backward-compatible model field names if provided
        if 'user' in kwargs and 'customer' not in kwargs:
            kwargs['customer'] = kwargs.pop('user')
        if 'party_size' in kwargs and 'guests_count' not in kwargs:
            kwargs['guests_count'] = kwargs.pop('party_size')
        if 'customer_name' in kwargs and 'guest_name' not in kwargs:
            kwargs['guest_name'] = kwargs.pop('customer_name')
        if 'customer_phone' in kwargs and 'guest_phone' not in kwargs:
            kwargs['guest_phone'] = kwargs.pop('customer_phone')
        if 'customer_email' in kwargs and 'guest_email' not in kwargs:
            kwargs['guest_email'] = kwargs.pop('customer_email')
        if 'reservation_number' in kwargs and 'reference_code' not in kwargs:
            kwargs['reference_code'] = kwargs.pop('reservation_number')
        super().__init__(*args, **kwargs)

    # Property aliases for modern API callers
    @property
    def reservation_number(self) -> str:
        return self.reference_code

    @reservation_number.setter
    def reservation_number(self, value: str):
        self.reference_code = value

    @property
    def user(self):
        return self.customer

    @user.setter
    def user(self, value):
        self.customer = value

    @property
    def customer_name(self) -> str:
        return self.guest_name

    @customer_name.setter
    def customer_name(self, value: str):
        self.guest_name = value

    @property
    def customer_phone(self) -> str:
        return self.guest_phone

    @customer_phone.setter
    def customer_phone(self, value: str):
        self.guest_phone = value

    @property
    def customer_email(self) -> str:
        return self.guest_email

    @customer_email.setter
    def customer_email(self, value: str):
        self.guest_email = value

    @property
    def party_size(self) -> int:
        return self.guests_count

    @party_size.setter
    def party_size(self, value: int):
        self.guests_count = value

    @classmethod
    def generate_reservation_number(cls) -> str:
        date_str = timezone.now().strftime("%Y%m%d")
        rand_str = uuid.uuid4().hex[:6].upper()
        return f"RES-{date_str}-{rand_str}"

    def calculate_end_time(self):
        if not self.reservation_time:
            return None
        dummy_dt = datetime.combine(self.reservation_date, self.reservation_time)
        return (dummy_dt + timedelta(minutes=self.duration_minutes)).time()

    def mark_confirmed(self):
        self.status = self.Status.CONFIRMED
        self.save(update_fields=["status", "updated_at"])

    def mark_seated(self, table=None):
        self.status = self.Status.SEATED
        self.seated_at = timezone.now()
        if table:
            self.table = table
            self.save(update_fields=["status", "seated_at", "table", "updated_at"])
        else:
            self.save(update_fields=["status", "seated_at", "updated_at"])

    def mark_completed(self):
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at", "updated_at"])

    def mark_no_show(self):
        self.status = self.Status.NO_SHOW
        self.save(update_fields=["status", "updated_at"])

    def mark_cancelled(self, reason=""):
        self.status = self.Status.CANCELLED
        self.cancellation_reason = reason
        self.cancelled_at = timezone.now()
        self.save(update_fields=["status", "cancellation_reason", "cancelled_at", "updated_at"])

    def save(self, *args, **kwargs):
        # 1. Normalize status string to lowercase
        if self.status:
            self.status = str(self.status).lower()

        # 2. Reference code generation
        if not self.reference_code:
            num = self.generate_reservation_number()
            while Reservation.objects.filter(reference_code=num).exists():
                num = self.generate_reservation_number()
            self.reference_code = num

        # 3. Synchronize time_slot and reservation_time
        if self.reservation_time and not self.time_slot:
            self.time_slot = self.reservation_time.strftime("%H:%M")
        elif self.time_slot and not self.reservation_time:
            try:
                parts = str(self.time_slot).strip().split(':')
                if len(parts) >= 2:
                    self.reservation_time = time(int(parts[0]), int(parts[1]))
            except Exception:
                pass

        # 4. Calculate end_time
        if not self.end_time and self.reservation_time:
            self.end_time = self.calculate_end_time()

        super().save(*args, **kwargs)

    def __str__(self):
        table_str = f" [Table {self.table.number}]" if self.table else ""
        slot_str = self.time_slot or (self.reservation_time.strftime('%H:%M') if self.reservation_time else "")
        return f"{self.reference_code} - {self.guest_name} ({self.guests_count} guests on {self.reservation_date} at {slot_str}){table_str}"


class ReservationNotification(models.Model):
    """
    Log of reservation confirmation, reminder, and status update notifications.
    """
    class NotificationType(models.TextChoices):
        CONFIRMATION = "CONFIRMATION", "Booking Confirmation"
        REMINDER = "REMINDER", "Booking Reminder"
        STATUS_UPDATE = "STATUS_UPDATE", "Status Update"
        CANCELLATION = "CANCELLATION", "Cancellation Confirmation"

    class Channel(models.TextChoices):
        SMS = "SMS", "SMS"
        EMAIL = "EMAIL", "Email"
        IN_APP = "IN_APP", "In-App"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="notifications"
    )
    recipient = models.CharField(max_length=255)
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices
    )
    channel = models.CharField(
        max_length=15,
        choices=Channel.choices,
        default=Channel.SMS
    )
    title = models.CharField(max_length=150)
    message = models.TextField()
    is_sent = models.BooleanField(default=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sent_at"]
        verbose_name = "Reservation Notification"
        verbose_name_plural = "Reservation Notifications"

    def __str__(self):
        return f"[{self.channel}] {self.get_notification_type_display()} to {self.recipient}"
