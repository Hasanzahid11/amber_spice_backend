from django.contrib import admin
from .models import KitchenStation, KitchenScreen, KitchenBumpLog


@admin.register(KitchenStation)
class KitchenStationAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'slug',
        'color_code',
        'display_order',
        'default_prep_time_minutes',
        'is_active',
        'created_at',
    )
    list_filter = ('is_active',)
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(KitchenScreen)
class KitchenScreenAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'screen_type',
        'station',
        'auto_refresh_seconds',
        'warning_threshold_pct',
        'critical_delay_minutes',
        'sound_alerts_enabled',
        'is_active',
    )
    list_filter = ('screen_type', 'is_active', 'sound_alerts_enabled')
    search_fields = ('name', 'device_identifier')


@admin.register(KitchenBumpLog)
class KitchenBumpLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'order',
        'action',
        'from_status',
        'to_status',
        'performed_by',
        'station',
    )
    list_filter = ('action', 'station', 'created_at')
    search_fields = ('order__order_number', 'notes')
    readonly_fields = (
        'id',
        'order',
        'action',
        'item',
        'station',
        'performed_by',
        'from_status',
        'to_status',
        'notes',
        'created_at',
    )

