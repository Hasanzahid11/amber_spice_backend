from django.contrib import admin
from .models import (
    DiningArea,
    Table,
    RestaurantTable,
    ReservationSchedule,
    ReservationSetting,
    Reservation,
    ReservationNotification,
)


@admin.register(DiningArea)
class DiningAreaAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_order', 'is_active', 'created_at')
    list_filter = ('is_active',)
    list_editable = ('display_order', 'is_active')
    search_fields = ('name', 'description')


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = (
        'number',
        'capacity',
        'min_capacity',
        'max_capacity',
        'shape',
        'dining_area',
        'section',
        'status',
        'guest_name',
        'time_slot',
        'is_active',
    )
    list_filter = ('status', 'dining_area', 'section', 'shape', 'capacity', 'is_active')
    list_editable = ('status', 'is_active')
    search_fields = ('number', 'guest_name', 'current_order')
    actions = ['release_tables']

    @admin.action(description="Release selected tables to Available")
    def release_tables(self, request, queryset):
        for table in queryset:
            table.release()
        self.message_user(request, f"{queryset.count()} table(s) released to available.")


@admin.register(ReservationSchedule)
class ReservationScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'day_of_week',
        'lunch_start',
        'lunch_end',
        'dinner_start',
        'dinner_end',
        'is_closed',
    )
    list_filter = ('is_closed',)
    list_editable = ('is_closed',)


@admin.register(ReservationSetting)
class ReservationSettingAdmin(admin.ModelAdmin):
    list_display = (
        'standard_duration_minutes',
        'large_party_duration_minutes',
        'min_party_size',
        'max_party_size',
        'min_advance_minutes',
        'max_advance_days',
        'auto_confirm_max_guests',
        'cancellation_deadline_hours',
    )


class ReservationNotificationInline(admin.TabularInline):
    model = ReservationNotification
    extra = 0
    readonly_fields = ('recipient', 'notification_type', 'channel', 'title', 'message', 'is_sent', 'sent_at')
    can_delete = False


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        'reference_code',
        'guest_name',
        'guest_phone',
        'table',
        'dining_area',
        'reservation_date',
        'time_slot',
        'guests_count',
        'status',
        'created_at',
    )
    list_filter = ('status', 'reservation_date', 'dining_area', 'table__section', 'table')
    search_fields = ('reference_code', 'guest_name', 'guest_phone', 'guest_email')
    date_hierarchy = 'reservation_date'
    actions = ['confirm_reservations', 'seat_reservations', 'complete_reservations', 'mark_as_no_show']
    inlines = [ReservationNotificationInline]

    @admin.action(description="Confirm selected reservations")
    def confirm_reservations(self, request, queryset):
        count = 0
        for res in queryset:
            res.mark_confirmed()
            count += 1
        self.message_user(request, f"{count} reservation(s) confirmed.")

    @admin.action(description="Seat selected reservations (Occupy Tables)")
    def seat_reservations(self, request, queryset):
        for res in queryset:
            res.mark_seated()
            if res.table:
                res.table.seat_party(guest_name=res.guest_name, time_slot=res.time_slot)
        self.message_user(request, f"{queryset.count()} reservation(s) seated.")

    @admin.action(description="Complete selected reservations (Release Tables)")
    def complete_reservations(self, request, queryset):
        for res in queryset:
            res.mark_completed()
            if res.table:
                res.table.release()
        self.message_user(request, f"{queryset.count()} reservation(s) completed.")

    @admin.action(description="Mark selected reservations as No-Show")
    def mark_as_no_show(self, request, queryset):
        for res in queryset:
            res.mark_no_show()
            if res.table and res.table.guest_name == res.guest_name:
                res.table.release()
        self.message_user(request, f"{queryset.count()} reservation(s) marked as no-show.")


@admin.register(ReservationNotification)
class ReservationNotificationAdmin(admin.ModelAdmin):
    list_display = ('reservation', 'recipient', 'notification_type', 'channel', 'title', 'is_sent', 'sent_at')
    list_filter = ('notification_type', 'channel', 'is_sent', 'sent_at')
    search_fields = ('recipient', 'title', 'reservation__reference_code')
