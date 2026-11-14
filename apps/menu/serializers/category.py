from django.core.validators import URLValidator
from django.db import transaction
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from ..models import Category


class CategorySerializer(serializers.ModelSerializer):
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
    image = serializers.ImageField(
        required=False,
        allow_null=True,
        write_only=True,
        help_text='Optional JPEG, PNG or WebP upload, up to 5 MB. Send using multipart/form-data.',
    )
    imageUrl = serializers.URLField(
        source='image_url',
        max_length=500,
        required=False,
        allow_blank=True,
        allow_null=True,
        validators=[URLValidator(schemes=['http', 'https'])],
        help_text='Public image URL. Upload an image file or provide an external HTTP/HTTPS URL.',
    )
    order = serializers.IntegerField(min_value=0, required=False)

    def validate_slug(self, value):
        if not value and self.instance:
            return self.instance.slug
        return value.lower()

    def validate_image(self, value):
        if value is None:
            return value
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError('Choose an image smaller than or equal to 5 MB.')
        image = value.image
        extensions = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp'}
        if image.format not in extensions:
            raise serializers.ValidationError('Only JPG, PNG and WebP images are supported.')
        if max(image.size) > 6000 or image.width * image.height > 25_000_000:
            raise serializers.ValidationError('Choose an image up to 6000 pixels per side and 25 megapixels.')
        value.name = f'category.{extensions[image.format]}'
        return value

    def validate(self, attrs):
        if attrs.get('image') and attrs.get('image_url'):
            raise serializers.ValidationError({'image': 'Upload an image or provide an image URL, not both.'})
        if 'image' in attrs:
            attrs['image_url'] = None
        elif 'image_url' in attrs:
            attrs['image'] = None
        return attrs

    def update(self, instance, validated_data):
        old_name = instance.image.name if instance.image else None
        old_storage = instance.image.storage
        instance = super().update(instance, validated_data)
        if old_name and old_name != instance.image.name:
            transaction.on_commit(lambda: old_storage.delete(old_name))
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.image:
            request = self.context.get('request')
            data['imageUrl'] = request.build_absolute_uri(instance.image.url) if request else instance.image.url
        return data

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'dishCount', 'imageUrl', 'image', 'description', 'order', 'is_active', 'created_at']
        read_only_fields = ['id', 'dishCount', 'created_at']
