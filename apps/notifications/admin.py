from django.contrib import admin
from .models import Notification, NotificationTemplate, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'title',
        'notification_type',
        'channel',
        'recipient',
        'recipient_email',
        'recipient_phone',
        'status',
        'is_read',
    )
    list_filter = (
        'notification_type',
        'channel',
        'status',
        'is_read',
        'created_at',
    )
    search_fields = (
        'title',
        'message',
        'recipient_email',
        'recipient_phone',
        'recipient__username',
    )
    readonly_fields = (
        'id',
        'recipient',
        'recipient_email',
        'recipient_phone',
        'recipient_role',
        'notification_type',
        'channel',
        'title',
        'message',
        'data',
        'status',
        'error_message',
        'is_read',
        'read_at',
        'sent_at',
        'created_at',
        'updated_at',
    )


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'event_type',
        'channel',
        'title_template',
        'is_active',
        'updated_at',
    )
    list_filter = ('channel', 'is_active')
    search_fields = ('event_type', 'title_template', 'body_template')


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'email_enabled',
        'sms_enabled',
        'whatsapp_enabled',
        'push_enabled',
        'order_updates',
        'inventory_alerts',
        'admin_alerts',
    )
    list_filter = ('email_enabled', 'sms_enabled', 'whatsapp_enabled', 'push_enabled')
    search_fields = ('user__username', 'user__email', 'user__phone')

