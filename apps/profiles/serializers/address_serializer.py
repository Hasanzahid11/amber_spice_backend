from rest_framework import serializers
from apps.profiles.models import UserAddress


class UserAddressSerializer(serializers.ModelSerializer):
    labelDisplay = serializers.CharField(source='get_label_display', read_only=True)
    formattedAddress = serializers.SerializerMethodField()

    class Meta:
        model = UserAddress
        fields = [
            'id',
            'label',
            'labelDisplay',
            'recipient_name',
            'recipient_phone',
            'address_line1',
            'address_line2',
            'city',
            'county_or_state',
            'postal_code',
            'delivery_instructions',
            'is_default',
            'formattedAddress',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_formattedAddress(self, obj) -> str:
        parts = [obj.address_line1]
        if obj.address_line2:
            parts.append(obj.address_line2)
        parts.append(f"{obj.city}, {obj.postal_code}")
        return ", ".join(parts)

