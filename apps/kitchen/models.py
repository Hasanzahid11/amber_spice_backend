import uuid
from django.conf import settings
from django.db import models
from django.utils.text import slugify


class KitchenStation(models.Model):
    """
    Physical or logical kitchen preparation stations (e.g. Grill, Curry, Biryani, Tandoor, Expeditor).
    Used to route food items and filter station screens on the KDS.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, help_text="Station name (e.g. Curry Station, Grill, Biryani)")
    slug = models.SlugField(max_length=100, unique=True, blank=True, help_text="Station code matching dish station tags")
    description = models.TextField(blank=True)
    color_code = models.CharField(
        max_length=20,
        default="#E65100",
        help_text="Hex color code for KDS badge header (e.g. #D32F2F, #1976D2, #388E3C)"
    )
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, help_text="Active station receiving orders on KDS")
    default_prep_time_minutes = models.PositiveIntegerField(
        default=15,
        help_text="Standard prep time baseline in minutes"
    )
    printer_ip = models.CharField(
        max_length=50,
        blank=True,
        help_text="Network ticket printer IP or identifier for this station"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = 'Kitchen Station'
        verbose_name_plural = 'Kitchen Stations'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.slug})"


class KitchenScreen(models.Model):
    """
    Dedicated display terminals / screen configurations mounted in the kitchen or front-of-house pass.
    """
    class ScreenType(models.TextChoices):
        STATION = 'station', 'Station Screen (Station-Specific Items)'
        EXPEDITOR = 'expeditor', 'Expeditor / Pass Screen (All Order Items)'
        RUNNER = 'runner', 'Food Runner Screen (Ready Pickups)'
        CUSTOMER_FACING = 'customer_facing', 'Order Status Board (Customer Display)'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Screen terminal label (e.g. Main Kitchen Pass, Curry Station 1)")
    screen_type = models.CharField(
        max_length=20,
        choices=ScreenType.choices,
        default=ScreenType.EXPEDITOR,
        help_text="Role and display behavior of this screen"
    )
    station = models.ForeignKey(
        KitchenStation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='screens',
        help_text="Assign to a specific station to filter items (leave blank for all stations / expeditor)"
    )
    device_identifier = models.CharField(
        max_length=100,
        blank=True,
        help_text="Unique hardware ID, tablet serial, or browser fingerprint"
    )
    auto_refresh_seconds = models.PositiveIntegerField(
        default=10,
        help_text="KDS polling / refresh rate interval in seconds"
    )
    warning_threshold_pct = models.PositiveIntegerField(
        default=75,
        help_text="Percentage of target prep time elapsed before badge turns Yellow (Warning)"
    )
    critical_delay_minutes = models.PositiveIntegerField(
        default=10,
        help_text="Minutes overdue before badge flashes Red (Critical Delayed)"
    )
    sound_alerts_enabled = models.BooleanField(
        default=True,
        help_text="Play audio chime when new order arrives or order becomes critically delayed"
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Kitchen Screen'
        verbose_name_plural = 'Kitchen Screens'

    def __str__(self):
        station_text = f" - {self.station.name}" if self.station else " (All Stations)"
        return f"{self.name} [{self.get_screen_type_display()}]{station_text}"


class KitchenBumpLog(models.Model):
    """
    Immutable audit log recording every KDS ticket bump, recall, status change, and item tick.
    """
    class Action(models.TextChoices):
        START_PREP = 'start_prep', 'Start Preparing (New -> Preparing)'
        MARK_READY = 'mark_ready', 'Mark Ready (Preparing -> Ready)'
        RECALL = 'recall', 'Recall Ticket (Ready -> Preparing)'
        ITEM_READY = 'item_ready', 'Item Marked Ready'
        ITEM_UNREADY = 'item_unready', 'Item Reopened'
        SET_PRIORITY = 'set_priority', 'Set Priority'
        EXPEDITE = 'expedite', 'Expedited / Rush'
        ADD_NOTE = 'add_note', 'Kitchen Note Added'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='kitchen_bump_logs',
        help_text="Target order on KDS"
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    item = models.ForeignKey(
        'orders.OrderItem',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='kitchen_logs',
        help_text="Specific item if action is item-level"
    )
    station = models.ForeignKey(
        KitchenStation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Station where the action was taken"
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='kitchen_actions',
        help_text="Chef / Staff member who performed the action"
    )
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Kitchen Bump Log'
        verbose_name_plural = 'Kitchen Bump Logs'

    def __str__(self):
        return f"{self.created_at.strftime('%H:%M:%S')} - Order #{self.order.order_number}: {self.get_action_display()}"

