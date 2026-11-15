from django.contrib import admin
from .models import (
    PurchaseOrder,
    PurchaseOrderItem,
    StockWastage,
    StockTransfer,
    StockTransferItem,
    StockAuditCount,
    StockAuditItem,
)


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1
    fields = ('inventory_item', 'quantity_ordered', 'quantity_received', 'unit', 'unit_cost', 'total_cost', 'is_fully_received')
    readonly_fields = ('total_cost', 'is_fully_received')


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = (
        'po_number',
        'supplier',
        'status',
        'order_date',
        'expected_delivery_date',
        'actual_delivery_date',
        'total_cost',
        'created_by',
    )
    list_filter = ('status', 'order_date', 'supplier')
    search_fields = ('po_number', 'supplier__name', 'invoice_number', 'notes')
    inlines = [PurchaseOrderItemInline]
    readonly_fields = ('po_number', 'subtotal', 'total_cost', 'created_at', 'updated_at')


@admin.register(StockWastage)
class StockWastageAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'inventory_item',
        'quantity',
        'unit',
        'reason',
        'total_waste_cost',
        'logged_by',
    )
    list_filter = ('reason', 'created_at')
    search_fields = ('inventory_item__name', 'notes')
    readonly_fields = ('cost_per_unit', 'total_waste_cost', 'created_at')


class StockTransferItemInline(admin.TabularInline):
    model = StockTransferItem
    extra = 1


@admin.register(StockTransfer)
class StockTransferAdmin(admin.ModelAdmin):
    list_display = (
        'transfer_number',
        'from_location',
        'to_location',
        'status',
        'transferred_by',
        'created_at',
    )
    list_filter = ('status', 'created_at')
    search_fields = ('transfer_number', 'from_location', 'to_location')
    inlines = [StockTransferItemInline]
    readonly_fields = ('transfer_number', 'created_at')


class StockAuditItemInline(admin.TabularInline):
    model = StockAuditItem
    extra = 0
    readonly_fields = ('variance', 'unit_cost', 'variance_cost')


@admin.register(StockAuditCount)
class StockAuditCountAdmin(admin.ModelAdmin):
    list_display = (
        'audit_number',
        'name',
        'status',
        'audit_date',
        'total_expected_value',
        'total_actual_value',
        'total_variance_value',
        'performed_by',
    )
    list_filter = ('status', 'audit_date')
    search_fields = ('audit_number', 'name')
    inlines = [StockAuditItemInline]
    readonly_fields = ('audit_number', 'total_expected_value', 'total_actual_value', 'total_variance_value', 'created_at', 'reconciled_at')

