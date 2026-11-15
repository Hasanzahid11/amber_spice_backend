from django.contrib import admin
from .models import (
    InventoryItem,
    Recipe,
    RecipeIngredient,
    StockMovement,
    Supplier,
)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_name', 'phone', 'email', 'lead_time_days', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'contact_name', 'phone', 'email')


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'category',
        'current_stock',
        'minimum_stock',
        'reorder_level',
        'unit',
        'purchase_price',
        'status',
        'supplier',
        'expiry_date',
        'storage_location',
        'is_active',
        'last_restocked',
    )
    list_filter = ('category', 'is_active', 'unit', 'storage_location')
    list_editable = ('current_stock', 'minimum_stock', 'reorder_level', 'purchase_price', 'is_active')
    search_fields = ('name', 'supplier', 'batch_number', 'storage_location')


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 1
    fields = ('inventory_item', 'quantity', 'unit', 'notes', 'quantity_in_item_unit', 'cost')
    readonly_fields = ('quantity_in_item_unit', 'cost')


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'dish',
        'yield_portions',
        'total_cost',
        'cost_per_portion',
        'food_cost_percentage',
        'is_active',
    )
    list_filter = ('is_active',)
    search_fields = ('name', 'dish__name')
    inlines = [RecipeIngredientInline]


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        'inventory_item',
        'movement_type',
        'quantity',
        'previous_stock',
        'new_stock',
        'unit_cost',
        'total_cost',
        'reference',
        'order',
        'performed_by',
        'created_at',
    )
    list_filter = ('movement_type', 'created_at')
    search_fields = ('reference', 'inventory_item__name', 'notes')
    readonly_fields = ('created_at',)
