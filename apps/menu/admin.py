from django.contrib import admin
from .models import Category, Dish, DishExtraOption, DishPortionOption


class DishPortionOptionInline(admin.TabularInline):
    model = DishPortionOption
    extra = 1


class DishExtraOptionInline(admin.TabularInline):
    model = DishExtraOption
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order', 'is_active', 'dish_count')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('order', 'is_active')


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
    list_editable = ('price', 'is_available', 'is_bestseller', 'is_popular')
    list_filter = ('category', 'station', 'is_available', 'is_bestseller', 'is_popular')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [DishPortionOptionInline, DishExtraOptionInline]
    actions = ['make_available', 'make_unavailable']

    fieldsets = (
        ('Dish Identification', {
            'fields': ('category', 'name', 'slug', 'description', 'image_url')
        }),
        ('Pricing & Station', {
            'fields': ('price', 'station', 'prep_time', 'spicy_level')
        }),
        ('Availability & Badges', {
            'fields': ('is_available', 'is_bestseller', 'is_popular', 'is_special')
        }),
        ('Ingredients & Modifiers (Customization)', {
            'description': 'Configure ingredients customers can remove/add and modifier choices without coding.',
            'fields': ('dietary', 'available_ingredients', 'available_modifiers')
        }),
    )

    @admin.action(description="Mark selected dishes as Available")
    def make_available(self, request, queryset):
        count = queryset.update(is_available=True)
        self.message_user(request, f"{count} dish(es) marked as available.")

    @admin.action(description="Mark selected dishes as Unavailable (Sold Out)")
    def make_unavailable(self, request, queryset):
        count = queryset.update(is_available=False)
        self.message_user(request, f"{count} dish(es) marked as unavailable.")
