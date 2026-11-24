from django.db import models
from django.conf import settings


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        ORDER_CREATED = 'order_created', 'New Order'
        ORDER_STATUS = 'order_status', 'Order Status Changed'
        KITCHEN_ALERT = 'kitchen_alert', 'Kitchen Ticket Alert'
        KITCHEN_READY = 'kitchen_ready', 'Kitchen Order Ready'
        STOCK_ALERT = 'stock_alert', 'Low Stock Alert'
        CUSTOMER_ARRIVED = 'customer_arrived', 'Customer Arrived'
        RESERVATION_CREATED = 'reservation_created', 'New Table Reservation'
        RESERVATION_STATUS = 'reservation_status', 'Reservation Status Changed'
        CONTACT_MESSAGE = 'contact_message', 'Customer Contact Inquiry'
        SYSTEM = 'system', 'System Notice'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
    )
    target_role = models.CharField(max_length=30, blank=True, default='')  # 'admin', 'kitchen', 'delivery', or '' (all)
    type = models.CharField(max_length=50, choices=NotificationType.choices, default=NotificationType.ORDER_CREATED)
    title = models.CharField(max_length=200)
    message = models.TextField()
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications',
    )
    data = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['target_role', 'is_read', '-created_at']),
            models.Index(fields=['user', 'is_read', '-created_at']),
        ]

    def __str__(self):
        return f"[{self.type}] {self.title} ({'Read' if self.is_read else 'Unread'})"
