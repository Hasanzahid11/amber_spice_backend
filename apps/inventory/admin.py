from django.contrib import admin
from .models import InventoryItem


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
