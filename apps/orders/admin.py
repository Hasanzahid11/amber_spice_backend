from django.contrib import admin
from .models import Cart, CartItem, CustomerAddress, Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ('dish', 'name', 'quantity', 'price', 'station', 'customizations', 'special_instructions')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number',
        'customer_name',
        'customer_phone',
        'dining_type',
        'schedule_type',
        'scheduled_for',
        'status',
        'payment_status',
        'total_amount',
        'created_at',
    )
    list_filter = (
        'status',
        'dining_type',
        'schedule_type',
        'payment_status',
        'payment_method',
        'is_saved_order',
    )
    search_fields = (
        'order_number',
        'customer_name',
        'customer_phone',
        'customer_email',
        'delivery_address',
    )
    date_hierarchy = 'created_at'
    inlines = [OrderItemInline]
    actions = [
        'mark_as_preparing',
        'mark_as_ready',
        'mark_as_out_for_delivery',
        'mark_as_delivered',
        'mark_as_paid',
    ]

    fieldsets = (
        ('Order Identification', {
            'fields': ('order_number', 'customer', 'customer_name', 'customer_phone', 'customer_email')
        }),
        ('Dining & Schedule Options', {
            'fields': ('dining_type', 'schedule_type', 'scheduled_for', 'table_number')
        }),
        ('Delivery & Logistics', {
            'fields': ('delivery_address', 'assigned_delivery_staff', 'estimated_time_minutes', 'notes')
        }),
        ('Financials & Payment', {
            'fields': ('subtotal', 'delivery_fee', 'tax', 'total_amount', 'payment_method', 'payment_status')
        }),
        ('Order Lifecycle', {
            'fields': ('status', 'is_saved_order', 'saved_order_name')
        }),
    )

    @admin.action(description="Mark selected orders as Preparing")
    def mark_as_preparing(self, request, queryset):
        queryset.update(status=Order.Status.PREPARING)

    @admin.action(description="Mark selected orders as Ready")
    def mark_as_ready(self, request, queryset):
        queryset.update(status=Order.Status.READY)

    @admin.action(description="Mark selected orders as Out for Delivery")
    def mark_as_out_for_delivery(self, request, queryset):
        queryset.update(status=Order.Status.OUT_FOR_DELIVERY)

    @admin.action(description="Mark selected orders as Delivered")
    def mark_as_delivered(self, request, queryset):
        queryset.update(status=Order.Status.DELIVERED)

    @admin.action(description="Mark selected orders as Paid")
    def mark_as_paid(self, request, queryset):
        queryset.update(payment_status=Order.PaymentStatus.PAID)


@admin.register(CustomerAddress)
class CustomerAddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'label', 'recipient_name', 'phone', 'address_line1', 'city', 'eircode', 'is_default')
    list_filter = ('is_default', 'city')
    search_fields = ('user__username', 'user__email', 'address_line1', 'eircode', 'phone')


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'session_id', 'dining_type', 'items_count', 'subtotal', 'total_amount', 'updated_at')
    list_filter = ('dining_type', 'schedule_type')
    search_fields = ('session_id', 'user__username', 'user__email')
    inlines = [CartItemInline]
