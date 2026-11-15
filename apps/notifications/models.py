import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    """
    Core Notification record for customer and staff communication.
    Tracks delivery across In-App, Email, SMS, WhatsApp, and Web/Mobile Push.
    """
    class NotificationType(models.TextChoices):
        NEW_ORDER = 'new_order', 'New Order Placed'
        ORDER_ACCEPTED = 'order_accepted', 'Order Accepted'
        ORDER_PREPARING = 'order_preparing', 'Order Preparing'
        ORDER_READY = 'order_ready', 'Order Ready'
        ORDER_DISPATCHED = 'order_dispatched', 'Order Dispatched'
        ORDER_COMPLETED = 'order_completed', 'Order Completed'
        ORDER_CANCELLED = 'order_cancelled', 'Order Cancelled'
        PAYMENT_CONFIRMATION = 'payment_confirmation', 'Payment Confirmation'
        PAYMENT_FAILED = 'payment_failed', 'Payment Failed'
        LOW_INVENTORY = 'low_inventory', 'Low Inventory Alert'
        ADMIN_ALERT = 'admin_alert', 'Important Admin Alert'

    class Channel(models.TextChoices):
        IN_APP = 'in_app', 'In-App / Dashboard'
        EMAIL = 'email', 'Email'
        SMS = 'sms', 'SMS Text'
        WHATSAPP = 'whatsapp', 'WhatsApp'
        PUSH = 'push', 'Push Notification'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        DELIVERED = 'delivered', 'Delivered'
        FAILED = 'failed', 'Failed'
        READ = 'read', 'Read'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text="Target user (or null for guest / external recipient)"
    )
    recipient_email = models.EmailField(blank=True)
    recipient_phone = models.CharField(max_length=30, blank=True)
    recipient_role = models.CharField(
        max_length=30,
        blank=True,
        help_text="e.g. customer, admin, manager, kitchen, delivery"
    )

    notification_type = models.CharField(
        max_length=40,
        choices=NotificationType.choices,
        db_index=True
    )
    channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
        default=Channel.IN_APP
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Metadata payload (e.g. order_id, order_number, total, action_url)"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )
    error_message = models.TextField(blank=True, help_text="Error log if delivery failed")

    # Read tracking for in-app notifications
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    # Delivery timestamps
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['notification_type', 'created_at']),
        ]

    def __str__(self):
        dest = self.recipient_email or self.recipient_phone or (self.recipient.username if self.recipient else "Broadcast")
        return f"[{self.get_channel_display()}] {self.get_notification_type_display()} -> {dest} ({self.status})"

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            if self.status in [self.Status.SENT, self.Status.DELIVERED]:
                self.status = self.Status.READ
            self.save(update_fields=['is_read', 'read_at', 'status', 'updated_at'])


class NotificationTemplate(models.Model):
    """
    Customizable message templates with dynamic placeholders like {customer_name}, {order_number}, {total}.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(
        max_length=40,
        choices=Notification.NotificationType.choices,
        help_text="Event triggering this template"
    )
    channel = models.CharField(
        max_length=20,
        choices=Notification.Channel.choices,
        default=Notification.Channel.IN_APP
    )
    title_template = models.CharField(
        max_length=200,
        help_text="e.g. 'Order #{order_number} is being prepared!'"
    )
    body_template = models.TextField(
        help_text="e.g. 'Hi {customer_name}, our chefs have begun preparing your order #{order_number}.'"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('event_type', 'channel')
        ordering = ['event_type', 'channel']
        verbose_name = 'Notification Template'
        verbose_name_plural = 'Notification Templates'

    def __str__(self):
        return f"{self.get_event_type_display()} [{self.get_channel_display()}]"

    def render(self, context: dict) -> tuple[str, str]:
        """
        Substitutes variables inside title_template and body_template with provided context.
        """
        title = self.title_template
        body = self.body_template
        for key, val in context.items():
            placeholder = f"{{{key}}}"
            str_val = str(val) if val is not None else ""
            title = title.replace(placeholder, str_val)
            body = body.replace(placeholder, str_val)
        return title, body


class NotificationPreference(models.Model):
    """
    Per-user notification delivery settings.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=True)
    whatsapp_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)

    # Categories
    order_updates = models.BooleanField(default=True, help_text="Updates regarding order status changes")
    promotional_updates = models.BooleanField(default=True, help_text="Discounts, coupons, and seasonal offers")
    inventory_alerts = models.BooleanField(default=True, help_text="Staff only: alerts when ingredients run low")
    admin_alerts = models.BooleanField(default=True, help_text="Staff only: urgent system and operational notices")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'

    def __str__(self):
        return f"Preferences for {self.user.username}"

    @classmethod
    def get_or_create_for_user(cls, user):
        obj, _ = cls.objects.get_or_create(user=user)
        return obj

