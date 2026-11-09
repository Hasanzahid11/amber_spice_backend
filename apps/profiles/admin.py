from django.contrib import admin
from .models import UserAddress, UserPreferences, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'loyalty_tier', 'loyalty_points', 'date_of_birth', 'updated_at']
    list_filter = ['loyalty_tier', 'preferred_language']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(UserAddress)
class UserAddressAdmin(admin.ModelAdmin):
    list_display = ['user', 'label', 'address_line1', 'city', 'postal_code', 'is_default', 'updated_at']
    list_filter = ['label', 'is_default', 'city']
    search_fields = ['user__username', 'user__email', 'address_line1', 'postal_code', 'recipient_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ['user', 'spice_tolerance', 'is_vegetarian', 'is_vegan', 'is_halal_only', 'preferred_payment_method']
    list_filter = ['spice_tolerance', 'is_vegetarian', 'is_vegan', 'is_halal_only', 'is_gluten_free', 'is_nut_allergy']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['updated_at']

