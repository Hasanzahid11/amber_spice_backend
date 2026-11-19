from django.core.validators import URLValidator
from django.db import transaction
from rest_framework import serializers


class MenuImageSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True, write_only=True,
                                   help_text='JPEG, PNG or WebP upload, up to 5 MB. Use multipart/form-data.')
    imageUrl = serializers.URLField(source='image_url', max_length=500, required=False,
                                    allow_blank=True, allow_null=True,
                                    validators=[URLValidator(schemes=['http', 'https'])])

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
        value.name = f'image.{extensions[image.format]}'
        return value

    def validate(self, attrs):
        empty_url = None if self.Meta.model._meta.get_field('image_url').null else ''
        if attrs.get('image') and attrs.get('image_url'):
            raise serializers.ValidationError({'image': 'Upload an image or provide an image URL, not both.'})
        if 'image' in attrs:
            attrs['image_url'] = empty_url
        elif 'image_url' in attrs:
            attrs['image'] = None
            if attrs['image_url'] is None:
                attrs['image_url'] = empty_url
        return attrs

    def update(self, instance, validated_data):
        old_name, storage = instance.image.name, instance.image.storage
        instance = super().update(instance, validated_data)
        if old_name and old_name != instance.image.name:
            transaction.on_commit(lambda: storage.delete(old_name))
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.image:
            request = self.context.get('request')
            data['imageUrl'] = request.build_absolute_uri(instance.image.url) if request else instance.image.url
        return data
