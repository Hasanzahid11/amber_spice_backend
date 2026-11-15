from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    image_url = models.URLField(max_length=500, blank=True, null=True)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['order', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def dish_count(self):
        return self.dishes.filter(is_available=True).count()


class Dish(models.Model):
    class Station(models.TextChoices):
        BIRYANI = 'biryani', 'Biryani'
        CURRY = 'curry', 'Curry'
        GRILL = 'grill', 'Grill'
        BREADS = 'breads', 'Breads'
        DESSERT = 'dessert', 'Dessert'
        BEVERAGE = 'beverage', 'Beverage'

    category = models.ForeignKey(
        Category,
        related_name='dishes',
        on_delete=models.CASCADE
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image_url = models.URLField(max_length=500, blank=True)
    station = models.CharField(
        max_length=30,
        choices=Station.choices,
        default=Station.CURRY
    )
    spicy_level = models.IntegerField(
        choices=[(0, 'Non-Spicy'), (1, 'Mild'), (2, 'Medium'), (3, 'Extra Hot')],
        default=0
    )
    rating = models.FloatField(default=4.8)
    orders_count = models.PositiveIntegerField(default=0)
    is_available = models.BooleanField(default=True)
    is_bestseller = models.BooleanField(default=False)
    is_popular = models.BooleanField(default=False)
    is_special = models.BooleanField(default=False)
    prep_time = models.CharField(max_length=50, default='15-20 min')
    dietary = models.JSONField(default=list, blank=True)
    available_ingredients = models.JSONField(
        default=list,
        blank=True,
        help_text="List of ingredients customers can remove/add (e.g. ['Onions', 'Cilantro', 'Garlic', 'Chili', 'Nuts', 'Dairy'])"
    )
    available_modifiers = models.JSONField(
        default=dict,
        blank=True,
        help_text="Modifiers with choices (e.g. {'spice_level': ['Mild', 'Medium', 'Hot', 'Extra Hot'], 'preparation': ['Boneless', 'Bone-in']})"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']
        verbose_name_plural = 'Dishes'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} (${self.price})"


class DishPortionOption(models.Model):
    dish = models.ForeignKey(Dish, related_name='portion_options', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    price_delta = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.dish.name} - {self.name} (+${self.price_delta})"


class DishExtraOption(models.Model):
    dish = models.ForeignKey(Dish, related_name='extra_options', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.dish.name} - {self.name} (${self.price})"
