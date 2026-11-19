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
        'created_by',
    )
    list_filter = ('category', 'station', 'is_available', 'is_bestseller', 'is_popular')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [DishPortionOptionInline, DishExtraOptionInline]

    readonly_fields = ('created_by',)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
