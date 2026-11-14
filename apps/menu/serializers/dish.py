from decimal import Decimal
import json

from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from drf_spectacular.utils import extend_schema_field

from ..models import Dish
from .attribution import MenuCreatorSerializer, added_by
from .images import MenuImageSerializer
from .options import DishExtraOptionSerializer, DishPortionOptionSerializer


class DietaryField(serializers.ListField):
    def get_value(self, dictionary):
        if hasattr(dictionary, 'getlist') and self.field_name in dictionary:
            values = dictionary.getlist(self.field_name)
            if len(values) == 1 and values[0].lstrip().startswith('['):
                return values[0]
            return values
        return super().get_value(dictionary)

    def to_internal_value(self, data):
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except ValueError:
                raise serializers.ValidationError('Send dietary as a JSON array of labels.')
        return super().to_internal_value(data)


class DishSerializer(MenuImageSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')
    addedBy = serializers.SerializerMethodField()
    slug = serializers.SlugField(max_length=220, required=False, allow_blank=True,
                                 validators=[UniqueValidator(queryset=Dish.objects.all(), lookup='iexact')])
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    portionOptions = DishPortionOptionSerializer(source='portion_options', many=True, read_only=True)
    extraOptions = DishExtraOptionSerializer(source='extra_options', many=True, read_only=True)
    isAvailable = serializers.BooleanField(source='is_available', required=False)
    isBestseller = serializers.BooleanField(source='is_bestseller', required=False)
    isPopular = serializers.BooleanField(source='is_popular', required=False)
    isSpecial = serializers.BooleanField(source='is_special', required=False)
    prepTime = serializers.CharField(source='prep_time', max_length=50, required=False, allow_blank=True)
    spicyLevel = serializers.IntegerField(source='spicy_level', min_value=0, max_value=3, required=False)
    ordersCount = serializers.IntegerField(source='orders_count', read_only=True)
    dietary = DietaryField(child=serializers.ChoiceField(choices=[
        'halal', 'vegetarian', 'vegan', 'gluten-free', 'dairy-free',
    ]), required=False)

    @extend_schema_field(MenuCreatorSerializer(allow_null=True))
    def get_addedBy(self, instance):
        return added_by(instance, self.context)

    def validate_slug(self, value):
        return value.lower() if value else (self.instance.slug if self.instance else '')

    def validate_category(self, value):
        if not value.is_active and (not self.instance or self.instance.category_id != value.pk):
            raise serializers.ValidationError('Choose an active category.')
        return value

    class Meta:
        model = Dish
        fields = [
            'id', 'category', 'category_name', 'name', 'slug', 'description', 'price',
            'imageUrl', 'image', 'station', 'spicyLevel', 'rating', 'ordersCount',
            'isAvailable', 'isBestseller', 'isPopular', 'isSpecial', 'prepTime',
            'dietary', 'portionOptions', 'extraOptions', 'created_at', 'addedBy',
        ]
        read_only_fields = ['id', 'rating', 'created_at']


class DishAvailabilitySerializer(serializers.Serializer):
    is_available = serializers.BooleanField(required=False)


class DishAvailabilityResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    message = serializers.CharField(read_only=True)
    is_available = serializers.BooleanField(read_only=True)
