from rest_framework import serializers

from ..models import DishExtraOption, DishPortionOption


class DishPortionOptionSerializer(serializers.ModelSerializer):
    servingInfo = serializers.CharField(source='serving_info', required=False, allow_blank=True)
    priceDelta = serializers.DecimalField(
        source='price_delta',
        max_digits=8,
        decimal_places=2
    )
    inventoryMultiplier = serializers.DecimalField(
        source='inventory_multiplier',
        max_digits=5,
        decimal_places=2,
        required=False
    )

    class Meta:
        model = DishPortionOption
        fields = ['id', 'name', 'servingInfo', 'priceDelta', 'inventoryMultiplier']


class DishExtraOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DishExtraOption
        fields = ['id', 'name', 'price']
