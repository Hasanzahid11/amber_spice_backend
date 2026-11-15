import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from apps.menu.models import Dish, DishExtraOption, DishPortionOption


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
        TAKEAWAY = 'takeaway', 'Takeaway / Collection'
        COLLECTION = 'collection', 'Collection'
        DELIVERY = 'delivery', 'Delivery'

    class ScheduleType(models.TextChoices):
        ASAP = 'asap', 'ASAP (Immediate)'
        SCHEDULED = 'scheduled', 'Scheduled'

    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        NORMAL = 'normal', 'Normal'
        HIGH = 'high', 'High'
        URGENT = 'urgent', 'Urgent'

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
        blank=True,
        help_text='Customer account (null for guest checkout)'
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
    customer_email = models.EmailField(blank=True, help_text='Email for order confirmation & receipt')
    dining_type = models.CharField(
        max_length=20,
        choices=DiningType.choices,
        default=DiningType.DELIVERY
    )
    schedule_type = models.CharField(
        max_length=20,
        choices=ScheduleType.choices,
        default=ScheduleType.ASAP,
        help_text='ASAP or scheduled for a specific future time'
    )
    scheduled_for = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Requested delivery or collection time for scheduled orders'
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
        default=PaymentMethod.CARD
    )
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    delivery_address = models.TextField(blank=True)
    notes = models.TextField(blank=True, help_text='General order notes & drop-off instructions')
    is_saved_order = models.BooleanField(
        default=False,
        help_text='Marked by customer as a saved favorite order for 1-click reordering'
    )
    saved_order_name = models.CharField(
        max_length=100,
        blank=True,
        help_text='User label for saved favorite order'
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL
    )
    prepared_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
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

    @property
    def target_completion_time(self):
        from datetime import timedelta
        return self.created_at + timedelta(minutes=self.estimated_time_minutes)

    @property
    def time_remaining_minutes(self):
        remaining = int((self.target_completion_time - timezone.now()).total_seconds() // 60)
        return remaining

    @property
    def is_delayed(self) -> bool:
        if self.status in [self.Status.READY, self.Status.DELIVERED, self.Status.CANCELLED]:
            return False
        return self.time_remaining_minutes < 0

    @property
    def delay_minutes(self) -> int:
        if not self.is_delayed:
            return 0
        return abs(self.time_remaining_minutes)

    @property
    def delay_severity(self) -> str:
        if not self.is_delayed:
            return 'none'
        mins = self.delay_minutes
        if mins >= 15:
            return 'critical'
        if mins >= 5:
            return 'warning'
        return 'mild'

    @property
    def is_guest_order(self) -> bool:
        return self.customer is None


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    dish = models.ForeignKey(Dish, related_name='order_items', on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    station = models.CharField(max_length=30, default='curry')
    is_ready = models.BooleanField(default=False)
    prepared_at = models.DateTimeField(null=True, blank=True)
    customizations = models.JSONField(
        default=dict,
        blank=True,
        help_text="portion, extras, removed_ingredients, added_ingredients, modifiers"
    )
    special_instructions = models.TextField(
        blank=True,
        help_text='Item-specific instructions (e.g. no onions, extra sauce)'
    )

    def __str__(self):
        return f"{self.quantity}x {self.name} (${self.price * self.quantity})"

    @property
    def total_price(self) -> Decimal:
        return self.price * self.quantity


class CustomerAddress(models.Model):
    """
    Saved delivery addresses for registered customers to enable 1-click checkout.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='saved_addresses',
        on_delete=models.CASCADE
    )
    label = models.CharField(max_length=50, default='Home', help_text='e.g. Home, Work, Apartment')
    recipient_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, default='Dublin')
    eircode = models.CharField(max_length=20, blank=True, help_text='Eircode / Postal Code')
    delivery_instructions = models.TextField(blank=True, help_text='Gate codes or drop-off notes')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-created_at']
        verbose_name = 'Saved Customer Address'
        verbose_name_plural = 'Saved Customer Addresses'

    def save(self, *args, **kwargs):
        if self.is_default:
            CustomerAddress.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.label}: {self.address_line1}, {self.city}"


class Cart(models.Model):
    """
    Online shopping cart supporting both authenticated customers and guest sessions.
    Allows customers to add items, modify options, adjust quantities, and inspect prices.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='carts',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    session_id = models.CharField(max_length=64, blank=True, db_index=True)
    dining_type = models.CharField(
        max_length=20,
        choices=Order.DiningType.choices,
        default=Order.DiningType.DELIVERY
    )
    schedule_type = models.CharField(
        max_length=20,
        choices=Order.ScheduleType.choices,
        default=Order.ScheduleType.ASAP
    )
    scheduled_for = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    @property
    def items_count(self) -> int:
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self) -> Decimal:
        return sum(item.total_price for item in self.items.all())

    @property
    def delivery_fee(self) -> Decimal:
        if self.dining_type == Order.DiningType.DELIVERY:
            return Decimal('3.50')
        return Decimal('0.00')

    @property
    def tax(self) -> Decimal:
        return Decimal('0.00')

    @property
    def total_amount(self) -> Decimal:
        return self.subtotal + self.delivery_fee + self.tax

    def clear(self):
        self.items.all().delete()


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    dish = models.ForeignKey(Dish, related_name='cart_items', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    portion_option = models.ForeignKey(
        DishPortionOption,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    extra_options = models.ManyToManyField(DishExtraOption, blank=True)
    customizations = models.JSONField(
        default=dict,
        blank=True,
        help_text="removed_ingredients, added_ingredients, modifiers"
    )
    special_instructions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def unit_price(self) -> Decimal:
        price = self.dish.price
        if self.portion_option:
            price += self.portion_option.price_delta
        # Sum extras if available
        if self.pk:
            for extra in self.extra_options.all():
                price += extra.price
        return price

    @property
    def total_price(self) -> Decimal:
        return self.unit_price * self.quantity
