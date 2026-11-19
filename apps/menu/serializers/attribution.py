from rest_framework import serializers


class MenuCreatorSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    role = serializers.CharField(read_only=True)


def added_by(instance, context):
    """Expose creator attribution to menu managers without publishing staff data."""
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return None
    if not request.user.has_restaurant_permission('menu:manage'):
        return None
    creator = instance.created_by
    if not creator:
        return None
    return {'id': creator.pk, 'name': creator.get_full_name() or creator.username, 'role': creator.role}
