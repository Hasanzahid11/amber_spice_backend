from rest_framework import serializers

from ..models import Dish
from .options import DishExtraOptionSerializer, DishPortionOptionSerializer


class DishSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')
    portionOptions = DishPortionOptionSerializer(source='portion_options', many=True, read_only=True)
    extraOptions = DishExtraOptionSerializer(source='extra_options', many=True, read_only=True)
    imageUrl = serializers.CharField(source='image_url', required=False, allow_blank=True)
    isAvailable = serializers.BooleanField(source='is_available', required=False)
    isBestseller = serializers.BooleanField(source='is_bestseller', required=False)
    isPopular = serializers.BooleanField(source='is_popular', required=False)
    isSpecial = serializers.BooleanField(source='is_special', required=False)
    prepTime = serializers.CharField(source='prep_time', required=False)
    spicyLevel = serializers.IntegerField(source='spicy_level', required=False)
    ordersCount = serializers.IntegerField(source='orders_count', read_only=True)

    class Meta:
        model = Dish
        fields = [
            'id',
            'category',
            'category_name',
            'name',
            'slug',
            'description',
            'price',
            'imageUrl',
            'station',
            'spicyLevel',
            'rating',
            'ordersCount',
            'isAvailable',
            'isBestseller',
            'isPopular',
            'isSpecial',
            'prepTime',
            'dietary',
            'portionOptions',
            'extraOptions',
            'created_at',
        ]
