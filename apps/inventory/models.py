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
    cost_per_unit = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))
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

    @property
    def total_cost(self):
        cost = (self.current_stock * (self.cost_per_unit or Decimal('0.0000'))).quantize(Decimal('0.01'))
        return cost


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


class DishRecipe(models.Model):
    dish = models.ForeignKey(
        'menu.Dish',
        on_delete=models.CASCADE,
        related_name='recipe_items'
    )
    ingredient = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name='dish_recipes'
    )
    quantity = models.DecimalField(max_digits=10, decimal_places=3)  # Quantity per dish portion
    unit = models.CharField(max_length=30, blank=True)
    notes = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['dish', 'ingredient__name']
        unique_together = [['dish', 'ingredient']]
        verbose_name = 'Dish Recipe Item'
        verbose_name_plural = 'Dish Recipe Items'

    def __str__(self):
        return f"{self.dish.name} - {self.ingredient.name} ({self.quantity} {self.unit or self.ingredient.unit})"

    def save(self, *args, **kwargs):
        if not self.unit and self.ingredient:
            self.unit = self.ingredient.unit
        super().save(*args, **kwargs)

    @property
    def cost(self):
        unit_cost = self.ingredient.cost_per_unit or Decimal('0.0000')
        return (Decimal(str(self.quantity)) * unit_cost).quantize(Decimal('0.01'))


class StockTransaction(models.Model):
    class TransactionType(models.TextChoices):
        PURCHASE = 'PURCHASE', 'Purchase / Restock'
        CONSUMPTION = 'CONSUMPTION', 'Order Consumption'
        WASTAGE = 'WASTAGE', 'Wastage / Spoilage'
        ADJUSTMENT = 'ADJUSTMENT', 'Manual Adjustment'

    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    transaction_type = models.CharField(
        max_length=30,
        choices=TransactionType.choices,
        default=TransactionType.PURCHASE
    )
    quantity_delta = models.DecimalField(max_digits=10, decimal_places=3)  # + or -
    unit_cost = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    order = models.ForeignKey(
        'orders.Order',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='stock_transactions'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='stock_transactions'
    )
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Stock Transaction'
        verbose_name_plural = 'Stock Transactions'

    def __str__(self):
        return f"{self.item.name} | {self.transaction_type} | {self.quantity_delta} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
