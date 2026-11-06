from django.contrib import admin
from .models import StaffMember


@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'shift', 'status', 'assigned_section', 'phone')
    list_filter = ('role', 'shift', 'status')
    search_fields = ('name', 'phone', 'assigned_section')
