import uuid
from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone


class Promotion(models.Model):
    """
    Comprehensive Promotions and Discounts Model.
    Supports percentage, fixed amount, first-order, free delivery, BOGO,
    promo codes, minimum order value, time windows, and usage limits.
    """
    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', 'Percentage Discount'
        FIXED_AMOUNT = 'fixed_amount', 'Fixed Value Discount'
        FIRST_ORDER = 'first_order', 'First Order Discount'
        FREE_DELIVERY = 'free_delivery', 'Free Delivery'
        BOGO = 'bogo', 'Buy One Get One (BOGO)'

    class AppliesTo(models.TextChoices):
        ENTIRE_ORDER = 'entire_order', 'Entire Order'
        SPECIFIC_CATEGORIES = 'specific_categories', 'Specific Menu Categories'
        SPECIFIC_DISHES = 'specific_dishes', 'Specific Dishes'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, help_text="Promotion name (e.g. Welcome 15% Off, Weekend Free Delivery)")
    description = models.TextField(blank=True, help_text="Customer-facing description of terms and benefits")
    code = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Coupon code (e.g. WELCOME15, FREEDELIVERY). Leave blank for automatic promotions."
    )
    discount_type = models.CharField(
        max_length=30,
        choices=DiscountType.choices,
        default=DiscountType.PERCENTAGE
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Percentage discount (e.g. 15.00 for 15%) or fixed discount amount (e.g. 5.00 for €5)"
    )
    max_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Optional maximum discount cap for percentage discounts (e.g. 20% off up to max €15)"
    )
    minimum_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Minimum order subtotal required to qualify for this discount"
    )

    # Scope & Applicability
    applies_to = models.CharField(
        max_length=30,
        choices=AppliesTo.choices,
        default=AppliesTo.ENTIRE_ORDER
    )
    applicable_categories = models.ManyToManyField(
        'menu.Category',
        blank=True,
        related_name='promotions',
        help_text="Categories eligible for this discount if applies_to is 'specific_categories'"
    )
    applicable_dishes = models.ManyToManyField(
        'menu.Dish',
        blank=True,
        related_name='promotions',
        help_text="Dishes eligible for this discount if applies_to is 'specific_dishes'"
    )
    applicable_dining_types = models.JSONField(
        default=list,
        blank=True,
        help_text="Allowed dining types: ['delivery', 'takeaway', 'dine_in'] (leave empty for all)"
    )

    # BOGO Specific Configuration
    buy_dish = models.ForeignKey(
        'menu.Dish',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='bogo_buy_promotions',
        help_text="Dish required to buy for BOGO"
    )
    buy_quantity = models.PositiveIntegerField(default=1, help_text="Number of items customer must buy")
    get_dish = models.ForeignKey(
        'menu.Dish',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='bogo_get_promotions',
        help_text="Reward dish received in BOGO"
    )
    get_quantity = models.PositiveIntegerField(default=1, help_text="Number of reward items received")
    get_discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('100.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text="Discount percentage on the get_dish (100% = Free, 50% = Half Price)"
    )

    # Start and End Dates (Time-Limited Offers)
    start_date = models.DateTimeField(default=timezone.now, help_text="When the promotion becomes active")
    end_date = models.DateTimeField(null=True, blank=True, help_text="When the promotion expires")

    # Time-of-day and Day-of-week restrictions (e.g. Happy Hour 17:00-19:00, or Weekends)
    has_time_window = models.BooleanField(default=False)
    start_time = models.TimeField(null=True, blank=True, help_text="Start time of daily window")
    end_time = models.TimeField(null=True, blank=True, help_text="End time of daily window")
    days_of_week = models.JSONField(
        default=list,
        blank=True,
        help_text="Days of week (0=Mon, 6=Sun) where promotion is valid. Empty means all days."
    )

    # Usage Limits
    usage_limit_total = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum total redemptions allowed across all customers (null = unlimited)"
    )
    usage_limit_per_customer = models.PositiveIntegerField(
        default=1,
        help_text="Maximum times an individual customer can use this promo"
    )
    times_used = models.PositiveIntegerField(default=0, help_text="Counter of total times redeemed")

    # Customer & Eligibility Rules
    is_first_order_only = models.BooleanField(
        default=False,
        help_text="Restricted exclusively to new customers placing their very first order"
    )
    is_active = models.BooleanField(default=True, help_text="Active toggle for admin to pause/resume")
    is_featured = models.BooleanField(default=False, help_text="Featured on website homepage/cart")
    banner_message = models.CharField(
        max_length=255,
        blank=True,
        help_text="Banner announcement text (e.g. 'Use code WEEKEND20 for 20% off orders over €40!')"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Promotion'
        verbose_name_plural = 'Promotions'

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        if self.discount_type == self.DiscountType.FIRST_ORDER:
            self.is_first_order_only = True
        super().save(*args, **kwargs)

    def __str__(self):
        code_str = f" [{self.code}]" if self.code else " (Auto)"
        return f"{self.name}{code_str} ({self.get_discount_type_display()})"

    @property
    def is_expired(self) -> bool:
        if self.end_date and timezone.now() > self.end_date:
            return True
        return False

    @property
    def is_started(self) -> bool:
        return timezone.now() >= self.start_date

    @property
    def is_limit_reached(self) -> bool:
        if self.usage_limit_total is not None and self.times_used >= self.usage_limit_total:
            return True
        return False

    def is_valid_now(self) -> tuple[bool, str]:
        """
        Validates date window, total limit, active status, and time of day.
        """
        if not self.is_active:
            return False, "This promotion is currently paused or inactive."

        now = timezone.now()
        if now < self.start_date:
            return False, f"This promotion begins on {self.start_date.strftime('%Y-%m-%d %H:%M')}."

        if self.end_date and now > self.end_date:
            return False, f"This promotion expired on {self.end_date.strftime('%Y-%m-%d %H:%M')}."

        if self.is_limit_reached:
            return False, "This promotion has reached its maximum usage limit."

        # Day of week check
        if self.days_of_week and now.weekday() not in self.days_of_week:
            day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            valid_days = ", ".join([day_names[d] for d in self.days_of_week if d < 7])
            return False, f"This offer is only valid on: {valid_days}."

        # Time window check (Happy Hour)
        if self.has_time_window and self.start_time and self.end_time:
            current_time = now.time()
            if not (self.start_time <= current_time <= self.end_time):
                return False, f"This offer is only active between {self.start_time.strftime('%H:%M')} and {self.end_time.strftime('%H:%M')}."

        return True, "Valid"

    def is_eligible_customer(self, user=None, customer_phone: str = "", customer_email: str = "") -> tuple[bool, str]:
        """
        Verifies customer-specific limits and first-order checks.
        """
        from apps.orders.models import Order

        # Check First-Order Restriction
        if self.is_first_order_only or self.discount_type == self.DiscountType.FIRST_ORDER:
            prior_orders_q = Q()
            if user and user.is_authenticated:
                prior_orders_q |= Q(customer=user)
            if customer_phone:
                prior_orders_q |= Q(customer_phone=customer_phone)
            if customer_email:
                prior_orders_q |= Q(customer_email=customer_email)

            if prior_orders_q:
                prior_orders_count = Order.objects.filter(prior_orders_q).exclude(status=Order.Status.CANCELLED).count()
                if prior_orders_count > 0:
                    return False, "This offer is only valid for new customers on their first order."

        # Check Per-Customer Usage Limit
        if self.usage_limit_per_customer:
            usage_q = Q(promotion=self)
            user_filters = Q()
            if user and user.is_authenticated:
                user_filters |= Q(user=user)
            if customer_phone:
                user_filters |= Q(customer_phone=customer_phone)
            if customer_email:
                user_filters |= Q(customer_email=customer_email)

            if user_filters:
                customer_usages = PromotionUsage.objects.filter(usage_q & user_filters).count()
                if customer_usages >= self.usage_limit_per_customer:
                    return False, f"You have already redeemed this promotion the maximum allowed ({self.usage_limit_per_customer} time(s))."

        return True, "Eligible"

    def calculate_discount(
        self,
        subtotal: Decimal,
        delivery_fee: Decimal = Decimal('0.00'),
        dining_type: str = 'delivery',
        items: list = None
    ) -> tuple[Decimal, Decimal, str]:
        """
        Calculates the applicable discount based on order subtotal, delivery fee, and items.
        Returns: (discount_amount, new_delivery_fee, reason)
        """
        # Minimum order check
        if self.minimum_order_amount and subtotal < self.minimum_order_amount:
            needed = (self.minimum_order_amount - subtotal).quantize(Decimal('0.01'))
            return Decimal('0.00'), delivery_fee, f"Order minimum of €{self.minimum_order_amount} not met (add €{needed} more to qualify)."

        # Dining type check
        if self.applicable_dining_types and dining_type not in self.applicable_dining_types:
            return Decimal('0.00'), delivery_fee, f"This offer is not valid for {dining_type} orders."

        discount = Decimal('0.00')
        new_delivery_fee = delivery_fee

        if self.discount_type == self.DiscountType.FREE_DELIVERY:
            discount = delivery_fee
            new_delivery_fee = Decimal('0.00')
            return discount, new_delivery_fee, "Free delivery applied."

        elif self.discount_type in [self.DiscountType.PERCENTAGE, self.DiscountType.FIRST_ORDER]:
            # Calculate eligible subtotal
            eligible_subtotal = subtotal
            if self.applies_to == self.AppliesTo.SPECIFIC_CATEGORIES and items:
                cat_ids = set(self.applicable_categories.values_list('id', flat=True))
                eligible_subtotal = sum(
                    Decimal(str(it.get('price', 0))) * Decimal(str(it.get('quantity', 1)))
                    for it in items
                    if it.get('category_id') in cat_ids or it.get('dish_category_id') in cat_ids
                )
            elif self.applies_to == self.AppliesTo.SPECIFIC_DISHES and items:
                dish_ids = set(self.applicable_dishes.values_list('id', flat=True))
                eligible_subtotal = sum(
                    Decimal(str(it.get('price', 0))) * Decimal(str(it.get('quantity', 1)))
                    for it in items
                    if it.get('dish_id') in dish_ids
                )

            discount = (eligible_subtotal * (self.discount_value / Decimal('100.00'))).quantize(Decimal('0.01'))
            if self.max_discount_amount and discount > self.max_discount_amount:
                discount = self.max_discount_amount

            return discount, new_delivery_fee, f"{self.discount_value}% discount applied."

        elif self.discount_type == self.DiscountType.FIXED_AMOUNT:
            discount = min(self.discount_value, subtotal)
            return discount, new_delivery_fee, f"€{discount} discount applied."

        elif self.discount_type == self.DiscountType.BOGO:
            # Buy One Get One Logic
            if not items or not self.buy_dish_id:
                return Decimal('0.00'), delivery_fee, "No eligible BOGO items found in cart."

            # Count eligible buy dishes
            buy_count = sum(
                int(it.get('quantity', 1))
                for it in items
                if str(it.get('dish_id')) == str(self.buy_dish_id)
            )

            qualifying_sets = buy_count // max(1, self.buy_quantity)
            if qualifying_sets <= 0:
                return Decimal('0.00'), delivery_fee, f"Buy {self.buy_quantity} {self.buy_dish.name} to qualify for BOGO offer."

            # Calculate reward on get_dish
            target_dish = self.get_dish or self.buy_dish
            target_dish_price = target_dish.price or Decimal('0.00')

            free_items_count = qualifying_sets * self.get_quantity
            # Check if customer has get_dish in cart
            in_cart_get = sum(
                int(it.get('quantity', 1))
                for it in items
                if str(it.get('dish_id')) == str(target_dish.id)
            )
            discounted_count = min(free_items_count, in_cart_get)
            if discounted_count <= 0:
                return Decimal('0.00'), delivery_fee, f"Add {target_dish.name} to your cart to receive your BOGO reward!"

            pct = self.get_discount_percentage / Decimal('100.00')
            discount = (Decimal(discounted_count) * target_dish_price * pct).quantize(Decimal('0.01'))
            return discount, new_delivery_fee, f"BOGO: {discounted_count}x {target_dish.name} discounted."

        return Decimal('0.00'), delivery_fee, "Promotion evaluated."

    def record_redemption(
        self,
        order=None,
        user=None,
        customer_phone: str = "",
        customer_email: str = "",
        discount_applied: Decimal = Decimal('0.00')
    ) -> 'PromotionUsage':
        """
        Creates a PromotionUsage record and increments the times_used counter.
        """
        usage = PromotionUsage.objects.create(
            promotion=self,
            order=order,
            user=user if (user and user.is_authenticated) else None,
            customer_phone=customer_phone,
            customer_email=customer_email,
            discount_applied=discount_applied
        )
        self.times_used += 1
        self.save(update_fields=['times_used', 'updated_at'])
        return usage


class PromotionUsage(models.Model):
    """
    Log of individual promotion code redemptions linked to customers and orders.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name='usages')
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='promotion_usages',
        null=True,
        blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='promotion_usages'
    )
    customer_phone = models.CharField(max_length=30, blank=True)
    customer_email = models.EmailField(blank=True)
    discount_applied = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Promotion Usage'
        verbose_name_plural = 'Promotion Usages'

    def __str__(self):
        user_str = self.customer_phone or (self.user.username if self.user else "Guest")
        return f"{self.promotion.name} used by {user_str} (-€{self.discount_applied})"

