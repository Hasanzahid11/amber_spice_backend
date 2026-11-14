from django.contrib import admin

from ..models import Dish, DishExtraOption, DishPortionOption


class DishPortionOptionInline(admin.TabularInline):
    model = DishPortionOption
    extra = 1


class DishExtraOptionInline(admin.TabularInline):
    model = DishExtraOption
    extra = 1


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'category',
        'price',
        'station',
        'is_available',
        'is_bestseller',
        'is_popular',
        'orders_count',
    )
    list_filter = ('category', 'station', 'is_available', 'is_bestseller', 'is_popular')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [DishPortionOptionInline, DishExtraOptionInline]
