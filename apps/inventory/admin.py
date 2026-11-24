from django.contrib import admin
from .models import InventoryCategory, InventoryItem, DishRecipe, StockTransaction, StockAlert, WastageRecord


@admin.register(InventoryCategory)
class InventoryCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'category',
        'current_stock',
        'minimum_stock',
        'cost_per_unit',
        'unit',
        'status',
        'supplier',
        'last_restocked',
    )
    list_filter = ('category',)
    search_fields = ('name', 'supplier')


@admin.register(DishRecipe)
class DishRecipeAdmin(admin.ModelAdmin):
    list_display = ('dish', 'ingredient', 'quantity', 'unit', 'cost', 'created_at')
    list_filter = ('dish__category', 'ingredient__category')
    search_fields = ('dish__name', 'ingredient__name')


@admin.register(StockTransaction)
class StockTransactionAdmin(admin.ModelAdmin):
    list_display = ('item', 'transaction_type', 'quantity_delta', 'unit_cost', 'total_cost', 'balance_after', 'order', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('item__name', 'order__order_number', 'notes')


@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ('item', 'stock_remaining_percent', 'resolved', 'reported_by', 'created_at')
    list_filter = ('resolved', 'created_at')
    search_fields = ('item__name', 'note')


@admin.register(WastageRecord)
class WastageRecordAdmin(admin.ModelAdmin):
    list_display = ('item', 'quantity', 'reason', 'reported_by', 'created_at')
    list_filter = ('reason', 'created_at')
    search_fields = ('item__name', 'reason')

