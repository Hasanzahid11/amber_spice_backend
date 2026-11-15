from rest_framework import serializers
from django.db import IntegrityError, transaction
from apps.profiles.models import UserAddress


class UserAddressSerializer(serializers.ModelSerializer):
    labelDisplay = serializers.CharField(source='get_label_display', read_only=True)
    formattedAddress = serializers.SerializerMethodField()

    def validate(self, attrs):
        label = attrs.get('label', self.instance.label if self.instance else 'home')
        if label in ('home', 'work'):
            addresses = UserAddress.objects.filter(user=self.context['request'].user, label=label)
            if self.instance:
                addresses = addresses.exclude(pk=self.instance.pk)
            if addresses.exists():
                raise serializers.ValidationError({'label': f'You already have a {label.title()} address. Edit it instead.'})
        return attrs

    def create(self, validated_data):
        try:
            with transaction.atomic():
                return super().create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError({'label': 'A Home or Work address already exists. Reload and edit it instead.'})

    def update(self, instance, validated_data):
        try:
            with transaction.atomic():
                return super().update(instance, validated_data)
        except IntegrityError:
            raise serializers.ValidationError({'label': 'A Home or Work address already exists. Reload and edit it instead.'})

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
        extra_kwargs = {
            'label': {'help_text': 'One Home and one Work per account; multiple Other addresses allowed. Office is retained for legacy records.'},
        }

    def get_formattedAddress(self, obj) -> str:
        parts = [obj.address_line1]
        if obj.address_line2:
            parts.append(obj.address_line2)
        parts.append(f"{obj.city}, {obj.postal_code}")
        return ", ".join(parts)

