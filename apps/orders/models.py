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
    customer_email = models.EmailField(blank=True)
    customer_chat_token = models.UUIDField(default=uuid.uuid4, editable=False)
    client_request_id = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    request_fingerprint = models.CharField(max_length=64, blank=True, editable=False)
    scheduled_for = models.DateTimeField(null=True, blank=True)
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
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coupon_code = models.CharField(max_length=40, blank=True)
    delivery_address = models.TextField(blank=True)
    delivery_postal_code = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    estimated_time_minutes = models.PositiveIntegerField(default=25)
    pickup_code = models.CharField(max_length=16, blank=True, default='')
    pickup_rack = models.CharField(max_length=64, blank=True, default='')
    customer_arrived_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    payment_collected_at = models.DateTimeField(null=True, blank=True)
    payment_collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='collected_payments'
    )
    counter_notes = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.order_number:
            date_str = timezone.now().strftime('%Y%m%d')
            unique_suffix = uuid.uuid4().hex[:18].upper()
            self.order_number = f"ORD-{date_str}-{unique_suffix}"
        if self.dining_type == self.DiningType.TAKEAWAY and not self.pickup_code:
            import secrets
            self.pickup_code = f"TK-{secrets.randbelow(9000) + 1000}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_number} - {self.customer_name} (${self.total_amount})"

    @property
    def display_pickup_code(self):
        if self.pickup_code:
            return self.pickup_code
        if self.dining_type == self.DiningType.TAKEAWAY:
            return f"TK-{self.id:04d}" if self.id else "TK-0001"
        return ""

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


class OrderEvent(models.Model):
    order = models.ForeignKey(Order, related_name='events', on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=Order.Status.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']


class RiderProfile(models.Model):
    class Vehicle(models.TextChoices):
        BICYCLE = 'bicycle', 'Bicycle'
        MOTORBIKE = 'motorbike', 'Motorbike'
        CAR = 'car', 'Car'
        WALKING = 'walking', 'Walking'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name='rider_profile', on_delete=models.CASCADE)
    on_duty = models.BooleanField(default=False)
    vehicle_type = models.CharField(max_length=20, choices=Vehicle.choices, default=Vehicle.BICYCLE)
    vehicle_registration = models.CharField(max_length=30, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class DeliveryJob(models.Model):
    class Stage(models.TextChoices):
        UNASSIGNED = 'unassigned', 'Awaiting assignment'
        ASSIGNED = 'assigned', 'Assigned'
        ACCEPTED = 'accepted', 'Accepted'
        PICKED_UP = 'picked_up', 'Picked up'
        ARRIVED = 'arrived', 'Arrived'
        RETURNING = 'returning', 'Returning to restaurant'
        RETURNED = 'returned', 'Returned to restaurant'
        DELIVERED = 'delivered', 'Delivered'
        CANCELLED = 'cancelled', 'Cancelled'

    order = models.OneToOneField(Order, related_name='delivery_job', on_delete=models.CASCADE)
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.UNASSIGNED)
    accepted_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cash_collected_at = models.DateTimeField(null=True, blank=True)
    return_requested_at = models.DateTimeField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    handed_over_at = models.DateTimeField(null=True, blank=True)
    handed_over_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='kitchen_handovers')
    handover_code = models.CharField(max_length=12, blank=True, editable=False)
    bag_count = models.PositiveSmallIntegerField(default=0)
    packed_items = models.JSONField(default=list, blank=True)
    bags_sealed = models.BooleanField(default=False)
    pickup_verified_at = models.DateTimeField(null=True, blank=True)
    delivery_verified_at = models.DateTimeField(null=True, blank=True)
    customer_confirmed_receipt = models.BooleanField(default=False)
    customer_confirmed_at = models.DateTimeField(null=True, blank=True)
    customer_payment_marked_at = models.DateTimeField(null=True, blank=True)
    customer_payment_medium = models.CharField(max_length=30, blank=True)
    issue_code = models.CharField(max_length=30, blank=True)
    issue_note = models.CharField(max_length=1000, blank=True)
    issue_reported_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class DeliveryEvent(models.Model):
    order = models.ForeignKey(Order, related_name='delivery_events', on_delete=models.CASCADE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=30)
    note = models.CharField(max_length=1200, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']


class DeliveryMessage(models.Model):
    order = models.ForeignKey(Order, related_name='delivery_messages', on_delete=models.CASCADE)
    rider = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='delivery_conversations')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='sent_delivery_messages')
    sender_role = models.CharField(max_length=10, choices=[('customer', 'Customer'), ('rider', 'Rider')])
    sender_name = models.CharField(max_length=150)
    body = models.CharField(max_length=2000)
    client_message_id = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        constraints = [models.UniqueConstraint(fields=['order', 'rider', 'sender_role', 'client_message_id'], name='unique_delivery_message_retry')]
