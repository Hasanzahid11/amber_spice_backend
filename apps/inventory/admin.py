from django.contrib import admin
from .models import InventoryCategory, InventoryItem


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
        'unit',
        'status',
        'supplier',
        'last_restocked',
    )
    list_filter = ('category',)
    search_fields = ('name', 'supplier')
