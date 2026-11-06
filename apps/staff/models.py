from django.conf import settings
from django.db import models


class StaffMember(models.Model):
    class Role(models.TextChoices):
        HEAD_CHEF = 'Head Chef', 'Head Chef'
        SOUS_CHEF = 'Sous Chef', 'Sous Chef'
        STATION_COOK = 'Station Cook', 'Station Cook'
        FLOOR_MANAGER = 'Floor Manager', 'Floor Manager'
        HOST = 'Host', 'Host'
        SERVER = 'Server', 'Server'

    class Shift(models.TextChoices):
        MORNING = 'Morning (10:00 - 16:00)', 'Morning (10:00 - 16:00)'
        EVENING = 'Evening (16:00 - 23:00)', 'Evening (16:00 - 23:00)'
        FULL_DAY = 'Full Day', 'Full Day'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        BREAK = 'break', 'Break'
        OFF_DUTY = 'off-duty', 'Off Duty'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_profile'
    )
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=50, choices=Role.choices, default=Role.SERVER)
    shift = models.CharField(max_length=50, choices=Shift.choices, default=Shift.MORNING)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.ACTIVE)
    avatar = models.URLField(max_length=500, blank=True)
    assigned_section = models.CharField(max_length=100, default='Main Floor')
    phone = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - {self.role} ({self.assigned_section})"
