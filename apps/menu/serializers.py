from rest_framework import serializers
from .models import Category, Dish, DishExtraOption, DishPortionOption


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


class CategorySerializer(serializers.ModelSerializer):
    dishCount = serializers.IntegerField(source='dish_count', read_only=True)
    imageUrl = serializers.CharField(source='image_url', required=False, allow_blank=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'dishCount', 'imageUrl', 'description', 'order', 'is_active']


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
    availableIngredients = serializers.JSONField(source='available_ingredients', required=False)
    availableModifiers = serializers.JSONField(source='available_modifiers', required=False)

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
            'availableIngredients',
            'availableModifiers',
            'portionOptions',
            'extraOptions',
            'created_at',
        ]

