from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    orderId = serializers.IntegerField(source='order_id', read_only=True)
    targetRole = serializers.CharField(source='target_role', read_only=True)
    isRead = serializers.BooleanField(source='is_read')
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id',
            'type',
            'title',
            'message',
            'orderId',
            'targetRole',
            'isRead',
            'data',
            'createdAt',
        ]
        read_only_fields = ['id', 'type', 'title', 'message', 'orderId', 'targetRole', 'data', 'createdAt']
