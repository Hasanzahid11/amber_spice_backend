from decimal import Decimal
from django.db import models
from django.conf import settings


class InventoryCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Inventory Category'
        verbose_name_plural = 'Inventory Categories'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            from django.utils.text import slugify
            base_slug = slugify(self.name) or 'category'
            slug = base_slug
            counter = 1
            while InventoryCategory.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class InventoryItem(models.Model):
    class Category(models.TextChoices):
        MEAT_POULTRY = 'Meat & Poultry', 'Meat & Poultry'
        SPICES_SEASONING = 'Spices & Seasoning', 'Spices & Seasoning'
        DAIRY = 'Dairy', 'Dairy'
        PRODUCE = 'Produce', 'Produce'
        PANTRY = 'Pantry', 'Pantry'

    class Status(models.TextChoices):
        OPTIMAL = 'optimal', 'Optimal'
        LOW = 'low', 'Low'
        CRITICAL = 'critical', 'Critical'

    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100, default='Pantry')
    category_ref = models.ForeignKey(
        InventoryCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='items'
    )
    current_stock = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_stock = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=30, default='kg')  # kg, ltr, bags, packs, etc.
    supplier = models.CharField(max_length=200, blank=True)
    last_restocked = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.current_stock} {self.unit})"

    def save(self, *args, **kwargs):
        if not self.category and self.category_ref:
            self.category = self.category_ref.name
        elif self.category and not self.category_ref:
            cat = InventoryCategory.objects.filter(name__iexact=self.category).first()
            if cat:
                self.category_ref = cat
        super().save(*args, **kwargs)

    @property
    def status(self):
        if self.current_stock <= (self.minimum_stock * Decimal('0.4')):
            return self.Status.CRITICAL
        elif self.current_stock <= self.minimum_stock:
            return self.Status.LOW
        return self.Status.OPTIMAL


class StockAlert(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT)
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    stock_remaining_percent = models.PositiveSmallIntegerField()
    note = models.TextField(blank=True)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class WastageRecord(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=200)
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
