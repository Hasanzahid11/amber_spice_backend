from rest_framework import serializers

from ..models import DishExtraOption, DishPortionOption


class DishPortionOptionSerializer(serializers.ModelSerializer):
    priceDelta = serializers.DecimalField(
        source='price_delta',
        max_digits=8,
        decimal_places=2
    )

    class Meta:
        model = DishPortionOption
        fields = ['id', 'name', 'priceDelta']


class DishExtraOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DishExtraOption
        fields = ['id', 'name', 'price']
