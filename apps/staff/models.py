from datetime import date, datetime, timedelta
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone


class StaffMember(models.Model):
    """
    Staff profile representing restaurant employees across kitchen, front-of-house,
    delivery, and management. Supports shifts, attendance, section assignments, and contacts.
    """
    class Role(models.TextChoices):
        HEAD_CHEF = 'Head Chef', 'Head Chef'
        SOUS_CHEF = 'Sous Chef', 'Sous Chef'
        STATION_COOK = 'Station Cook', 'Station Cook'
        FLOOR_MANAGER = 'Floor Manager', 'Floor Manager'
        HOST = 'Host', 'Host'
        SERVER = 'Server', 'Server'
        CASHIER = 'Cashier', 'Cashier'
        DELIVERY_DRIVER = 'Delivery Driver', 'Delivery Driver'
        BARTENDER = 'Bartender', 'Bartender / Barista'
        KITCHEN_PORTER = 'Kitchen Porter', 'Kitchen Porter / Cleaner'
        STAFF = 'Staff', 'General Staff'

    class Shift(models.TextChoices):
        MORNING = 'Morning (10:00 - 16:00)', 'Morning (10:00 - 16:00)'
        EVENING = 'Evening (16:00 - 23:00)', 'Evening (16:00 - 23:00)'
        FULL_DAY = 'Full Day', 'Full Day'
        CUSTOM = 'Custom Shift', 'Custom Shift'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active (On Duty)'
        BREAK = 'break', 'On Break'
        OFF_DUTY = 'off-duty', 'Off Duty'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_profile',
        help_text="Linked user login account"
    )
    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True, help_text="Contact email address")
    role = models.CharField(max_length=50, choices=Role.choices, default=Role.SERVER)
    shift = models.CharField(max_length=50, choices=Shift.choices, default=Shift.MORNING)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.ACTIVE)
    avatar = models.URLField(max_length=500, blank=True)
    assigned_section = models.CharField(
        max_length=100,
        default='Main Floor',
        help_text="Floor zone, kitchen station, or delivery hub"
    )
    phone = models.CharField(max_length=30, blank=True, help_text="Irish mobile or contact phone")
    hourly_rate = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Hourly pay rate in EUR"
    )
    hire_date = models.DateField(null=True, blank=True, help_text="Date joined restaurant team")
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Active employee status (uncheck when staff member leaves)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Staff Member'
        verbose_name_plural = 'Staff Members'

    def save(self, *args, **kwargs):
        # Auto-sync with linked User model if available
        if self.user:
            if not self.name:
                self.name = self.user.get_full_name() or self.user.username
            if not self.email and self.user.email:
                self.email = self.user.email
            if not self.phone and self.user.phone:
                self.phone = self.user.phone
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.get_role_display()} ({self.assigned_section})"

    @property
    def is_on_duty(self) -> bool:
        return self.status == self.Status.ACTIVE

    @property
    def active_attendance(self):
        """Returns currently active open attendance record (clocked in without clock out)."""
        return self.attendance_records.filter(clock_out__isnull=True).order_by('-clock_in').first()

    def clock_in(self, notes=""):
        """Clocks the employee into their shift."""
        open_att = self.active_attendance
        if open_att:
            return open_att

        self.status = self.Status.ACTIVE
        self.save(update_fields=['status', 'updated_at'])

        return StaffAttendance.objects.create(
            staff_member=self,
            clock_in=timezone.now(),
            status=StaffAttendance.Status.ON_DUTY,
            notes=notes
        )

    def clock_out(self, notes=""):
        """Clocks the employee out and calculates hours worked."""
        att = self.active_attendance
        now = timezone.now()

        if att:
            att.clock_out = now
            delta = now - att.clock_in
            hours = Decimal(str(delta.total_seconds() / 3600.0)).quantize(Decimal('0.01'))
            att.total_hours = max(Decimal('0.00'), hours)
            att.status = StaffAttendance.Status.COMPLETED
            if notes:
                att.notes = f"{att.notes}\n{notes}".strip()
            att.save(update_fields=['clock_out', 'total_hours', 'status', 'notes'])

        self.status = self.Status.OFF_DUTY
        self.save(update_fields=['status', 'updated_at'])
        return att

    def toggle_break(self):
        """Switches between on break and active duty."""
        att = self.active_attendance
        if self.status == self.Status.ACTIVE:
            self.status = self.Status.BREAK
            if att:
                att.status = StaffAttendance.Status.ON_BREAK
                att.save(update_fields=['status'])
        elif self.status == self.Status.BREAK:
            self.status = self.Status.ACTIVE
            if att:
                att.status = StaffAttendance.Status.ON_DUTY
                att.save(update_fields=['status'])
        self.save(update_fields=['status', 'updated_at'])
        return self.status


class StaffShift(models.Model):
    """
    Roster & Shift Schedules assigning staff members to dates, time windows, and sections.
    """
    class ShiftStatus(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        CONFIRMED = 'confirmed', 'Confirmed'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
        SICK_LEAVE = 'sick_leave', 'Sick Leave / Absent'

    staff_member = models.ForeignKey(
        StaffMember,
        related_name='shifts',
        on_delete=models.CASCADE
    )
    shift_date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    title = models.CharField(max_length=100, blank=True, help_text="e.g. Lunch Service, Dinner Rush, Kitchen Prep")
    station = models.CharField(max_length=100, blank=True, help_text="Specific station (e.g. Biryani & Grill, Front POS)")
    status = models.CharField(max_length=20, choices=ShiftStatus.choices, default=ShiftStatus.SCHEDULED)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['shift_date', 'start_time']
        verbose_name = 'Staff Shift'
        verbose_name_plural = 'Staff Shifts'

    def __str__(self):
        return f"{self.staff_member.name} - {self.shift_date} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"


class StaffAttendance(models.Model):
    """
    Clock in/clock out timestamps and working hours audit for payroll and attendance tracking.
    """
    class Status(models.TextChoices):
        ON_DUTY = 'on_duty', 'On Duty'
        ON_BREAK = 'on_break', 'On Break'
        COMPLETED = 'completed', 'Completed'

    staff_member = models.ForeignKey(
        StaffMember,
        related_name='attendance_records',
        on_delete=models.CASCADE
    )
    clock_in = models.DateTimeField(default=timezone.now)
    clock_out = models.DateTimeField(null=True, blank=True)
    break_minutes = models.PositiveIntegerField(default=0)
    total_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ON_DUTY)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-clock_in']
        verbose_name = 'Staff Attendance'
        verbose_name_plural = 'Staff Attendance Records'

    def __str__(self):
        out_str = self.clock_out.strftime('%H:%M') if self.clock_out else 'Active'
        return f"{self.staff_member.name} [{self.clock_in.strftime('%Y-%m-%d %H:%M')} - {out_str}]"
