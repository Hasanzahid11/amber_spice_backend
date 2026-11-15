from django.conf import settings
from django.db import models, transaction


class UserAddress(models.Model):
    class AddressLabel(models.TextChoices):
        HOME = 'home', 'Home'
        WORK = 'work', 'Work'
        OFFICE = 'office', 'Office'
        OTHER = 'other', 'Other'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_addresses'
    )
    label = models.CharField(
        max_length=30,
        choices=AddressLabel.choices,
        default=AddressLabel.HOME
    )
    recipient_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Name of the person receiving the order"
    )
    recipient_phone = models.CharField(
        max_length=30,
        blank=True,
        help_text="Contact number for delivery courier"
    )
    address_line1 = models.CharField(
        max_length=255,
        help_text="Street address, house/flat number"
    )
    address_line2 = models.CharField(
        max_length=255,
        blank=True,
        help_text="Apartment, suite, unit, building, floor"
    )
    city = models.CharField(max_length=100, default='Dublin')
    county_or_state = models.CharField(max_length=100, default='Co. Dublin')
    postal_code = models.CharField(
        max_length=20,
        help_text="Eircode or Postal Code (e.g. D02 X285)"
    )
    delivery_instructions = models.TextField(
        blank=True,
        help_text="Specific gate code, building instructions, or drop-off location"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Set as default delivery address for 1-click orders"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'label'], condition=models.Q(label__in=['home', 'work']),
                name='unique_home_work_address_per_user',
            ),
        ]
        verbose_name = 'Saved Address'
        verbose_name_plural = 'Saved Addresses'

    def __str__(self):
        return f"{self.get_label_display()} - {self.address_line1}, {self.city} ({self.postal_code})"

    def save(self, *args, **kwargs):
        # If this is the user's first address, automatically make it default
        if not self.pk and not UserAddress.objects.filter(user=self.user).exists():
            self.is_default = True

        if self.is_default:
            with transaction.atomic():
                UserAddress.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

