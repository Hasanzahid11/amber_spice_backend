from django.contrib import admin
from .models import Promotion, PromotionUsage


class PromotionUsageInline(admin.TabularInline):
    model = PromotionUsage
    extra = 0
    readonly_fields = ('order', 'user', 'customer_phone', 'customer_email', 'discount_applied', 'created_at')
    can_delete = False


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'code',
        'discount_type',
        'discount_value',
        'minimum_order_amount',
        'times_used',
        'usage_limit_total',
        'start_date',
        'end_date',
        'is_active',
        'is_featured',
    )
    list_filter = (
        'discount_type',
        'is_active',
        'is_first_order_only',
        'is_featured',
        'start_date',
        'end_date',
    )
    search_fields = ('name', 'code', 'description', 'banner_message')
    filter_horizontal = ('applicable_categories', 'applicable_dishes')
    inlines = [PromotionUsageInline]
    readonly_fields = ('times_used', 'created_at', 'updated_at')


@admin.register(PromotionUsage)
class PromotionUsageAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'promotion',
        'order',
        'user',
        'customer_phone',
        'discount_applied',
    )
    list_filter = ('promotion', 'created_at')
    search_fields = (
        'promotion__name',
        'promotion__code',
        'order__order_number',
        'customer_phone',
        'customer_email',
        'user__username',
    )
    readonly_fields = (
        'id',
        'promotion',
        'order',
        'user',
        'customer_phone',
        'customer_email',
        'discount_applied',
        'created_at',
    )

