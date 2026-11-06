from django.contrib import admin
from .models import Reservation, Table


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ('number', 'capacity', 'status', 'guest_name', 'time_slot')
    list_filter = ('status', 'capacity')
    search_fields = ('number', 'guest_name')


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        'guest_name',
        'guest_phone',
        'table',
        'reservation_date',
        'time_slot',
        'guests_count',
        'status',
    )
    list_filter = ('status', 'reservation_date', 'table')
    search_fields = ('guest_name', 'guest_phone', 'guest_email')
