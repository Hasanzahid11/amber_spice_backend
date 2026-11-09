from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import UserPreferences, UserProfile

User = get_user_model()


@receiver(post_save, sender=User)
def create_or_sync_user_profile(sender, instance, created, **kwargs):
    """
    Gold standard signal receiver:
    Ensures every user automatically has a UserProfile and UserPreferences object.
    """
    if created:
        UserProfile.objects.get_or_create(user=instance)
        UserPreferences.objects.get_or_create(user=instance)
    else:
        # Guarantee profile existence for any legacy/pre-existing users
        if not hasattr(instance, 'profile'):
            UserProfile.objects.get_or_create(user=instance)
        if not hasattr(instance, 'preferences'):
            UserPreferences.objects.get_or_create(user=instance)

