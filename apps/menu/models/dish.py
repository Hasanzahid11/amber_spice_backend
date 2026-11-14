from django.db import models
from django.utils.text import slugify

from .category import Category


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
