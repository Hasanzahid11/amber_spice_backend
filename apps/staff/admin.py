from django.contrib import admin
from .models import StaffAttendance, StaffMember, StaffShift


class StaffShiftInline(admin.TabularInline):
    model = StaffShift
    extra = 1
    fields = ('shift_date', 'start_time', 'end_time', 'title', 'station', 'status')


class StaffAttendanceInline(admin.TabularInline):
    model = StaffAttendance
    extra = 0
    fields = ('clock_in', 'clock_out', 'break_minutes', 'total_hours', 'status')
    readonly_fields = ('clock_in', 'clock_out', 'total_hours')


@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'role',
        'shift',
        'status',
        'assigned_section',
        'phone',
        'hourly_rate',
        'is_active',
        'created_at',
    )
    list_filter = ('role', 'shift', 'status', 'is_active', 'assigned_section')
    list_editable = ('status', 'is_active')
    search_fields = ('name', 'phone', 'email', 'assigned_section')
    inlines = [StaffShiftInline, StaffAttendanceInline]


@admin.register(StaffShift)
class StaffShiftAdmin(admin.ModelAdmin):
    list_display = ('staff_member', 'shift_date', 'start_time', 'end_time', 'title', 'station', 'status')
    list_filter = ('shift_date', 'status', 'station')
    search_fields = ('title', 'station', 'staff_member__name')
    date_hierarchy = 'shift_date'


@admin.register(StaffAttendance)
class StaffAttendanceAdmin(admin.ModelAdmin):
    list_display = ('staff_member', 'clock_in', 'clock_out', 'break_minutes', 'total_hours', 'status')
    list_filter = ('status', 'clock_in')
    search_fields = ('staff_member__name', 'notes')
    date_hierarchy = 'clock_in'
