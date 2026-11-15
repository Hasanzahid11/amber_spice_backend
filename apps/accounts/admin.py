from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import RolePermissionConfig, User, UserCustomPermission


class UserCustomPermissionInline(admin.StackedInline):
    model = UserCustomPermission
    can_delete = False
    verbose_name = 'Custom Permission Overrides'


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'phone', 'is_vip', 'is_staff', 'is_active')
    list_filter = ('role', 'is_vip', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone')
    fieldsets = UserAdmin.fieldsets + (
        ('Restaurant Profile', {'fields': ('role', 'phone', 'avatar', 'is_vip')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Restaurant Profile', {'fields': ('role', 'phone', 'avatar', 'is_vip')}),
    )
    inlines = [UserCustomPermissionInline]


@admin.register(RolePermissionConfig)
class RolePermissionConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'permission_count', 'is_customizable', 'updated_at')
    list_filter = ('is_customizable',)
    search_fields = ('name', 'role')
    actions = ['reset_selected_roles_to_defaults']

    def permission_count(self, obj):
        return len(obj.permissions)
    permission_count.short_description = 'Permissions Count'

    @admin.action(description="Reset selected roles to system default permissions")
    def reset_selected_roles_to_defaults(self, request, queryset):
        for config in queryset:
            config.reset_to_default()
        self.message_user(request, f"Successfully reset permissions for {queryset.count()} role(s).")


@admin.register(UserCustomPermission)
class UserCustomPermissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'granted_count', 'revoked_count', 'updated_at')
    search_fields = ('user__username', 'user__email', 'user__phone')

    def granted_count(self, obj):
        return len(obj.granted_permissions)

    def revoked_count(self, obj):
        return len(obj.revoked_permissions)
