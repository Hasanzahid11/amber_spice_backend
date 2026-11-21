from django.conf import settings
from django.db import models
import uuid


class Table(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = 'available', 'Available'
        OCCUPIED = 'occupied', 'Occupied'
        RESERVED = 'reserved', 'Reserved'

    number = models.CharField(max_length=20, unique=True)
    capacity = models.PositiveIntegerField(default=4)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE
    )
    current_order = models.CharField(max_length=50, blank=True, null=True)
    guest_name = models.CharField(max_length=120, blank=True, null=True)
    time_slot = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        ordering = ['number']

    def __str__(self):
        return f"Table {self.number} ({self.capacity} seats) - {self.get_status_display()}"


class Reservation(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        SEATED = 'seated', 'Seated'
        CANCELLED = 'cancelled', 'Cancelled'
        COMPLETED = 'completed', 'Completed'
        NO_SHOW = 'no_show', 'No-Show'

    table = models.ForeignKey(
        Table,
        related_name='reservations',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='reservations',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    guest_name = models.CharField(max_length=120)
    guest_phone = models.CharField(max_length=30)
    guest_email = models.EmailField(blank=True)
    guests_count = models.PositiveIntegerField(default=2)
    reservation_date = models.DateField()
    time_slot = models.CharField(max_length=50)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CONFIRMED
    )
    special_requests = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    guest_arrived_at = models.DateTimeField(null=True, blank=True)
    booking_reference = models.CharField(max_length=32, unique=True, null=True, blank=True, editable=False)

    class Meta:
        ordering = ['reservation_date', 'time_slot']
        constraints = [models.UniqueConstraint(fields=['table', 'reservation_date', 'time_slot'], condition=models.Q(status__in=['pending', 'confirmed', 'seated']), name='one_active_table_booking_per_slot')]

    def save(self, *args, **kwargs):
        if not self.booking_reference:
            self.booking_reference = uuid.uuid4().hex
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Reservation for {self.guest_name} on {self.reservation_date} at {self.time_slot}"
