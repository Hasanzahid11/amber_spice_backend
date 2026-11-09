from django.conf import settings
from django.db import models


class UserPreferences(models.Model):
    class SpiceLevel(models.TextChoices):
        MILD = 'mild', 'Mild'
        MEDIUM = 'medium', 'Medium'
        HOT = 'hot', 'Hot'
        EXTRA_HOT = 'extra_hot', 'Extra Hot'

    class PaymentPreference(models.TextChoices):
        CARD = 'card', 'Credit/Debit Card'
        CASH_ON_DELIVERY = 'cash_on_delivery', 'Cash on Delivery'
        STRIPE = 'stripe', 'Stripe Online'
        APPLE_PAY = 'apple_pay', 'Apple Pay'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='preferences'
    )

    # Dietary & Allergy Preferences
    is_vegetarian = models.BooleanField(default=False)
    is_vegan = models.BooleanField(default=False)
    is_halal_only = models.BooleanField(default=False)
    is_gluten_free = models.BooleanField(default=False)
    is_dairy_free = models.BooleanField(default=False)
    is_nut_allergy = models.BooleanField(default=False)
    spice_tolerance = models.CharField(
        max_length=20,
        choices=SpiceLevel.choices,
        default=SpiceLevel.MEDIUM
    )
    special_dietary_notes = models.TextField(
        blank=True,
        help_text="Custom allergies, dietary constraints or kitchen preparation notes"
    )

    # Communication Preferences
    email_order_updates = models.BooleanField(default=True)
    sms_order_updates = models.BooleanField(default=True)
    promotional_emails = models.BooleanField(default=False)
    promotional_sms = models.BooleanField(default=False)

    # Ordering Preferences
    preferred_payment_method = models.CharField(
        max_length=30,
        choices=PaymentPreference.choices,
        default=PaymentPreference.CARD
    )
    include_plastic_cutlery = models.BooleanField(
        default=False,
        help_text="Opt-in to receive disposable cutlery and napkins"
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Preferences'
        verbose_name_plural = 'User Preferences'

    def __str__(self):
        return f"Preferences of {self.user.username}"

