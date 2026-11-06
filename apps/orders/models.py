import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from apps.menu.models import Dish


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PREPARING = 'preparing', 'Preparing'
        READY = 'ready', 'Ready'
        OUT_FOR_DELIVERY = 'out_for_delivery', 'Out for Delivery'
        DELIVERED = 'delivered', 'Delivered'
        CANCELLED = 'cancelled', 'Cancelled'

    class DiningType(models.TextChoices):
        DINE_IN = 'dine-in', 'Dine-In'
        TAKEAWAY = 'takeaway', 'Takeaway'
        DELIVERY = 'delivery', 'Delivery'

    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        REFUNDED = 'refunded', 'Refunded'

    class PaymentMethod(models.TextChoices):
        CARD = 'card', 'Credit/Debit Card'
        CASH = 'cash', 'Cash'
        APPLE_PAY = 'apple-pay', 'Apple Pay'
        ONLINE = 'online', 'Online Payment'

    order_number = models.CharField(max_length=32, unique=True, blank=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='orders',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    assigned_delivery_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='assigned_deliveries',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Staff member assigned to deliver this order'
    )
    customer_name = models.CharField(max_length=120)
    customer_phone = models.CharField(max_length=30, blank=True)
    dining_type = models.CharField(
        max_length=20,
        choices=DiningType.choices,
        default=DiningType.DINE_IN
    )
    table_number = models.CharField(max_length=20, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH
    )
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    delivery_address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    estimated_time_minutes = models.PositiveIntegerField(default=25)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.order_number:
            date_str = timezone.now().strftime('%Y%m%d')
            unique_suffix = uuid.uuid4().hex[:5].upper()
            self.order_number = f"ORD-{date_str}-{unique_suffix}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_number} - {self.customer_name} (${self.total_amount})"

    @property
    def elapsed_minutes(self):
        delta = timezone.now() - self.created_at
        return int(delta.total_seconds() // 60)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    dish = models.ForeignKey(Dish, related_name='order_items', on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    station = models.CharField(max_length=30, default='curry')
    customizations = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.quantity}x {self.name} (${self.price * self.quantity})"
