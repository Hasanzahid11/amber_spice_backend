from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from drf_spectacular.utils import extend_schema_field

from ..models import Category
from .attribution import MenuCreatorSerializer, added_by
from .images import MenuImageSerializer


class CategorySerializer(MenuImageSerializer):
    addedBy = serializers.SerializerMethodField()

    @extend_schema_field(MenuCreatorSerializer(allow_null=True))
    def get_addedBy(self, instance):
        return added_by(instance, self.context)

    name = serializers.CharField(
        max_length=100,
        validators=[UniqueValidator(
            queryset=Category.objects.all(),
            lookup='iexact',
            message='A category with this name already exists.',
        )],
    )
    slug = serializers.SlugField(
        max_length=120,
        required=False,
        allow_blank=True,
        help_text='Optional unique URL slug. Generated from the name when omitted.',
        validators=[UniqueValidator(
            queryset=Category.objects.all(),
            lookup='iexact',
            message='A category with this slug already exists.',
        )],
    )
    dishCount = serializers.IntegerField(source='dish_count', read_only=True)
    order = serializers.IntegerField(min_value=0, required=False)

    def validate_slug(self, value):
        if not value and self.instance:
            return self.instance.slug
        return value.lower()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'dishCount', 'imageUrl', 'image', 'description', 'order', 'is_active', 'created_at', 'addedBy']
        read_only_fields = ['id', 'dishCount', 'created_at', 'addedBy']
