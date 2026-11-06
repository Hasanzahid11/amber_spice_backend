from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number',
        'customer_name',
        'dining_type',
        'table_number',
        'status',
        'payment_status',
        'total_amount',
        'created_at',
    )
    list_filter = ('status', 'dining_type', 'payment_status', 'payment_method')
    search_fields = ('order_number', 'customer_name', 'customer_phone')
    inlines = [OrderItemInline]
