from rest_framework import serializers
from .models import Notification, NotificationTemplate, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    notificationTypeDisplay = serializers.CharField(source='get_notification_type_display', read_only=True)
    channelDisplay = serializers.CharField(source='get_channel_display', read_only=True)
    statusDisplay = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id',
            'recipient',
            'recipient_email',
            'recipient_phone',
            'recipient_role',
            'notification_type',
            'notificationTypeDisplay',
            'channel',
            'channelDisplay',
            'title',
            'message',
            'data',
            'status',
            'statusDisplay',
            'error_message',
            'is_read',
            'read_at',
            'sent_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'status', 'error_message', 'read_at', 'sent_at', 'created_at', 'updated_at']


class NotificationTemplateSerializer(serializers.ModelSerializer):
    eventTypeDisplay = serializers.CharField(source='get_event_type_display', read_only=True)
    channelDisplay = serializers.CharField(source='get_channel_display', read_only=True)

    class Meta:
        model = NotificationTemplate
        fields = [
            'id',
            'event_type',
            'eventTypeDisplay',
            'channel',
            'channelDisplay',
            'title_template',
            'body_template',
            'is_active',
            'created_at',
            'updated_at',
        ]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            'id',
            'user',
            'email_enabled',
            'sms_enabled',
            'whatsapp_enabled',
            'push_enabled',
            'order_updates',
            'promotional_updates',
            'inventory_alerts',
            'admin_alerts',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class SendNotificationRequestSerializer(serializers.Serializer):
    notification_type = serializers.ChoiceField(choices=Notification.NotificationType.choices, default=Notification.NotificationType.ADMIN_ALERT)
    title = serializers.CharField(max_length=200)
    message = serializers.CharField()
    recipient_role = serializers.CharField(required=False, allow_blank=True, default='')
    recipient_email = serializers.EmailField(required=False, allow_blank=True, default='')
    recipient_phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default='')
    channels = serializers.ListField(child=serializers.ChoiceField(choices=Notification.Channel.choices), required=False, default=list)
    data = serializers.DictField(required=False, default=dict)

