from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    class LoyaltyTier(models.TextChoices):
        BRONZE = 'bronze', 'Bronze'
        SILVER = 'silver', 'Silver'
        GOLD = 'gold', 'Gold'
        PLATINUM = 'platinum', 'Platinum'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    bio = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    anniversary = models.DateField(null=True, blank=True)
    loyalty_points = models.PositiveIntegerField(default=0)
    loyalty_tier = models.CharField(
        max_length=20,
        choices=LoyaltyTier.choices,
        default=LoyaltyTier.BRONZE
    )
    default_delivery_instructions = models.TextField(
        blank=True,
        help_text="Default drop-off notes for Dublin courier (e.g. Ring doorbell, apartment code)"
    )
    preferred_language = models.CharField(max_length=10, default='en')
    emergency_contact = models.CharField(max_length=30, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"Profile of {self.user.username} ({self.loyalty_tier})"

    @property
    def completion_percentage(self) -> int:
        fields = [
            bool(self.user.first_name),
            bool(self.user.email),
            bool(self.user.phone),
            bool(self.user.avatar),
            bool(self.date_of_birth),
            bool(self.bio),
            bool(self.default_delivery_instructions),
            self.user.saved_addresses.filter(is_default=True).exists(),
        ]
        completed = sum(1 for f in fields if f)
        return int((completed / len(fields)) * 100)

    @property
    def next_tier_points(self) -> int:
        if self.loyalty_points < 500:
            return 500 - self.loyalty_points
        elif self.loyalty_points < 1500:
            return 1500 - self.loyalty_points
        elif self.loyalty_points < 3000:
            return 3000 - self.loyalty_points
        return 0

