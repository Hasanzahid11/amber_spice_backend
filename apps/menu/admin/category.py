from django.contrib import admin

from ..models import Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order', 'is_active', 'dish_count')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('order', 'is_active')
