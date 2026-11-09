from django.contrib.auth import get_user_model
from rest_framework import serializers
from apps.profiles.models import UserProfile, UserPreferences

User = get_user_model()


class ProfileService:
    @staticmethod
    def get_or_create_profile(user) -> UserProfile:
        profile, _ = UserProfile.objects.get_or_create(user=user)
        return profile

    @staticmethod
    def get_or_create_preferences(user) -> UserPreferences:
        preferences, _ = UserPreferences.objects.get_or_create(user=user)
        return preferences

    @staticmethod
    def update_profile(user, data: dict) -> UserProfile:
        profile = ProfileService.get_or_create_profile(user)
        user_updated = False

        # 1. Update Full Name or Name
        incoming_name = data.get('name') or data.get('fullName')
        if incoming_name is not None:
            name_parts = str(incoming_name).strip().split(maxsplit=1)
            user.first_name = name_parts[0] if name_parts else ''
            user.last_name = name_parts[1] if len(name_parts) > 1 else ''
            user_updated = True
        else:
            if 'first_name' in data:
                user.first_name = str(data['first_name']).strip()
                user_updated = True
            if 'last_name' in data:
                user.last_name = str(data['last_name']).strip()
                user_updated = True

        # 2. Update Email with uniqueness validation
        if 'email' in data and data['email']:
            new_email = str(data['email']).strip().lower()
            old_email = (user.email or '').strip().lower()
            if new_email != old_email:
                if User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
                    raise serializers.ValidationError({
                        'email': 'This email address is already in use by another account.'
                    })
                user.email = new_email
                # Keep username in sync if username was the old email
                if user.username.lower() == old_email:
                    if not User.objects.filter(username__iexact=new_email).exclude(pk=user.pk).exists():
                        user.username = new_email
                user_updated = True

        # 3. Update Phone
        if 'phone' in data:
            user.phone = str(data['phone']).strip() if data['phone'] else ''
            user_updated = True

        # 4. Update Avatar
        if 'avatar' in data:
            user.avatar = data['avatar']
            user_updated = True

        if user_updated:
            user.save()

        # 5. Update Profile specific fields
        profile_fields = [
            'bio',
            'date_of_birth',
            'anniversary',
            'default_delivery_instructions',
            'preferred_language',
            'emergency_contact',
        ]
        for field in profile_fields:
            if field in data:
                setattr(profile, field, data[field])

        profile.save()
        return profile

    @staticmethod
    def add_loyalty_points(user, points: int) -> UserProfile:
        profile = ProfileService.get_or_create_profile(user)
        profile.loyalty_points += max(0, points)

        # Upgrade tier based on accumulated points
        if profile.loyalty_points >= 3000:
            profile.loyalty_tier = UserProfile.LoyaltyTier.PLATINUM
        elif profile.loyalty_points >= 1500:
            profile.loyalty_tier = UserProfile.LoyaltyTier.GOLD
        elif profile.loyalty_points >= 500:
            profile.loyalty_tier = UserProfile.LoyaltyTier.SILVER
        else:
            profile.loyalty_tier = UserProfile.LoyaltyTier.BRONZE

        profile.save()
        return profile
