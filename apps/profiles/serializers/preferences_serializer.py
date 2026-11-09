from rest_framework import serializers
from apps.profiles.models import UserPreferences


class UserPreferencesSerializer(serializers.ModelSerializer):
    spiceToleranceDisplay = serializers.CharField(source='get_spice_tolerance_display', read_only=True)
    preferredPaymentDisplay = serializers.CharField(source='get_preferred_payment_method_display', read_only=True)

    class Meta:
        model = UserPreferences
        fields = [
            'id',
            'is_vegetarian',
            'is_vegan',
            'is_halal_only',
            'is_gluten_free',
            'is_dairy_free',
            'is_nut_allergy',
            'spice_tolerance',
            'spiceToleranceDisplay',
            'special_dietary_notes',
            'email_order_updates',
            'sms_order_updates',
            'promotional_emails',
            'promotional_sms',
            'preferred_payment_method',
            'preferredPaymentDisplay',
            'include_plastic_cutlery',
            'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']

