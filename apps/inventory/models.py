from django.db import models


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
    category = models.CharField(max_length=50, choices=Category.choices)
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

    @property
    def status(self):
        if self.current_stock <= (self.minimum_stock * 0.4):
            return self.Status.CRITICAL
        elif self.current_stock <= self.minimum_stock:
            return self.Status.LOW
        return self.Status.OPTIMAL
