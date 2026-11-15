from datetime import date, timedelta
from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Supplier(models.Model):
    """
    Suppliers and vendors providing ingredients, beverages, and packaging supplies.
    """
    name = models.CharField(max_length=200, unique=True)
    contact_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    lead_time_days = models.PositiveIntegerField(default=2, help_text="Delivery lead time in days")
    payment_terms = models.CharField(max_length=100, blank=True, default='Net 30')
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Supplier'
        verbose_name_plural = 'Suppliers'

    def __str__(self):
        return self.name

    @property
    def items_count(self) -> int:
        return self.inventory_items.filter(is_active=True).count()


class InventoryItem(models.Model):
    """
    Restaurant inventory items including raw meats, poultry, grains, produce,
    spices, sauces, drinks, packaging, and general supplies.
    Supports real-time stock levels, min/reorder alerts, purchase prices, batch/expiry tracking.
    """
    class Category(models.TextChoices):
        # Specific requested categories
        MEAT_POULTRY = 'Meat & Poultry', 'Meat & Poultry (Chicken, etc.)'
        BEEF_LAMB = 'Beef & Red Meat', 'Beef & Lamb'
        SEAFOOD = 'Seafood', 'Seafood & Fish'
        RICE_GRAINS = 'Rice & Grains', 'Rice & Grains'
        FLOUR_BAKERY = 'Flour & Bakery', 'Flour & Bakery'
        OILS_FATS = 'Oils & Fats', 'Cooking Oil & Fats'
        VEGETABLES = 'Vegetables', 'Vegetables & Fresh Produce'
        SAUCES = 'Sauces', 'Sauces, Pastes & Condiments'
        SPICES_SEASONING = 'Spices & Seasoning', 'Spices & Seasoning'
        DAIRY = 'Dairy', 'Dairy (Paneer, Milk, Curd, Butter)'
        DRINKS = 'Drinks', 'Drinks & Beverages'
        PACKAGING = 'Packaging Materials', 'Packaging & Takeaway Supplies'
        PANTRY = 'Pantry', 'Pantry & Dry Goods'
        PRODUCE = 'Produce', 'Produce'
        OTHER = 'Other Supplies', 'Other Ingredients & Supplies'

    class Status(models.TextChoices):
        OPTIMAL = 'optimal', 'Optimal'
        LOW = 'low', 'Low'
        CRITICAL = 'critical', 'Critical'
        OUT_OF_STOCK = 'out_of_stock', 'Out of Stock'

    class Unit(models.TextChoices):
        KG = 'kg', 'Kilogram (kg)'
        G = 'g', 'Gram (g)'
        LITRE = 'litre', 'Litre (l)'
        ML = 'ml', 'Millilitre (ml)'
        PIECES = 'pieces', 'Pieces (pcs)'
        PORTIONS = 'portions', 'Portions'
        PACKS = 'packs', 'Packs'
        BOXES = 'boxes', 'Boxes'
        BAGS = 'bags', 'Bags'
        BOTTLES = 'bottles', 'Bottles'
        CANS = 'cans', 'Cans'

    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100, choices=Category.choices)
    current_stock = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal('0.000'),
        help_text="Current physical on-hand quantity"
    )
    minimum_stock = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal('0.000'),
        help_text="Safety stock threshold"
    )
    reorder_level = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal('0.000'),
        help_text="Stock level triggering automatic reorder recommendations"
    )
    unit = models.CharField(
        max_length=30,
        default='kg',
        help_text="Primary inventory unit (kg, g, litre, ml, pieces, etc.)"
    )
    supplier = models.CharField(
        max_length=200,
        blank=True,
        help_text="Supplier or vendor name"
    )
    supplier_ref = models.ForeignKey(
        Supplier,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='inventory_items',
        help_text="Linked supplier profile"
    )
    purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Cost price per primary unit (e.g. €/kg)"
    )
    expiry_date = models.DateField(
        null=True,
        blank=True,
        help_text="Current batch expiry date where relevant"
    )
    batch_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Supplier lot / batch identification number"
    )
    storage_location = models.CharField(
        max_length=100,
        blank=True,
        help_text="Storage location (e.g. Walk-in Cooler, Dry Shelf B, Freezer)"
    )
    is_active = models.BooleanField(default=True)
    last_restocked = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Inventory Item'
        verbose_name_plural = 'Inventory Items'

    def save(self, *args, **kwargs):
        if self.supplier_ref and not self.supplier:
            self.supplier = self.supplier_ref.name
        # Default reorder_level to minimum_stock if not explicitly set
        if not self.reorder_level and self.minimum_stock:
            self.reorder_level = self.minimum_stock
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.current_stock} {self.unit})"

    @property
    def status(self) -> str:
        """Calculates real-time inventory health status."""
        if self.current_stock <= 0:
            return self.Status.CRITICAL

        threshold = self.minimum_stock if self.minimum_stock > 0 else self.reorder_level
        if threshold > 0:
            if self.current_stock <= (threshold * Decimal('0.4')):
                return self.Status.CRITICAL
            elif self.current_stock <= threshold:
                return self.Status.LOW

        return self.Status.OPTIMAL

    @property
    def reorder_needed(self) -> bool:
        """Flag indicating if stock is below safe reorder thresholds."""
        threshold = self.reorder_level if self.reorder_level > 0 else self.minimum_stock
        return self.current_stock <= threshold if threshold > 0 else False

    @property
    def is_expiring_soon(self) -> bool:
        """True if the item has an expiry date within the next 7 days."""
        if not self.expiry_date:
            return False
        return self.expiry_date <= (date.today() + timedelta(days=7))

    @property
    def stock_value(self) -> Decimal:
        """Total inventory asset value for this item."""
        return (self.current_stock * self.purchase_price).quantize(Decimal('0.01'))


class Recipe(models.Model):
    """
    Bill of Materials (BOM) linking a menu Dish to its constituent inventory ingredients.
    Enables automatic consumption tracking upon customer orders, accurate food costing,
    and waste reduction.
    """
    dish = models.OneToOneField(
        'menu.Dish',
        related_name='recipe',
        on_delete=models.CASCADE,
        help_text="The menu dish produced by this recipe"
    )
    name = models.CharField(max_length=200, blank=True)
    yield_portions = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Number of standard portions this recipe yields"
    )
    instructions = models.TextField(blank=True, help_text="Preparation / cooking notes for kitchen staff")
    prep_time_minutes = models.PositiveIntegerField(default=15)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['dish__name']
        verbose_name = 'Recipe / BOM'
        verbose_name_plural = 'Recipes / BOMs'

    def save(self, *args, **kwargs):
        if not self.name and self.dish:
            self.name = f"Recipe for {self.dish.name}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.yield_portions} portions)"

    @property
    def total_cost(self) -> Decimal:
        """Total ingredient cost required to prepare the full recipe yield."""
        return sum((ing.cost for ing in self.ingredients.all()), Decimal('0.00'))

    @property
    def cost_per_portion(self) -> Decimal:
        """Ingredient food cost per single customer portion."""
        if self.yield_portions > 0:
            return (self.total_cost / Decimal(self.yield_portions)).quantize(Decimal('0.01'))
        return Decimal('0.00')

    @property
    def food_cost_percentage(self) -> float:
        """Food cost percentage compared to the dish selling price."""
        if self.dish and self.dish.price > 0:
            return round(float(self.cost_per_portion / self.dish.price) * 100, 2)
        return 0.0


class RecipeIngredient(models.Model):
    """
    Single ingredient component in a Recipe BOM (e.g. 200g chicken, 100g rice, 20g sauce).
    Automatically handles unit conversions between recipe measures and warehouse stock units.
    """
    recipe = models.ForeignKey(
        Recipe,
        related_name='ingredients',
        on_delete=models.CASCADE
    )
    inventory_item = models.ForeignKey(
        InventoryItem,
        related_name='recipe_usages',
        on_delete=models.CASCADE
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        help_text="Quantity required for the recipe yield (e.g. 200 for 200g, 0.2 for 0.2kg)"
    )
    unit = models.CharField(
        max_length=30,
        help_text="Unit of measurement in recipe (e.g. g, kg, ml, litre, pieces)"
    )
    notes = models.CharField(
        max_length=150,
        blank=True,
        help_text="Prep details (e.g. diced, boneless, washed)"
    )

    class Meta:
        unique_together = ('recipe', 'inventory_item')
        ordering = ['inventory_item__name']
        verbose_name = 'Recipe Ingredient'
        verbose_name_plural = 'Recipe Ingredients'

    def __str__(self):
        return f"{self.quantity} {self.unit} {self.inventory_item.name} for {self.recipe.name}"

    @property
    def quantity_in_item_unit(self) -> Decimal:
        """Converts the recipe quantity to the inventory item's native storage unit."""
        from .utils import convert_quantity
        return convert_quantity(self.quantity, self.unit, self.inventory_item.unit)

    @property
    def cost(self) -> Decimal:
        """Calculates cost for this ingredient requirement."""
        return (self.quantity_in_item_unit * self.inventory_item.purchase_price).quantize(Decimal('0.01'))


class StockMovement(models.Model):
    """
    Complete audit trail of all inventory additions, order consumptions, waste/spoilage,
    and manual count reconciliations.
    """
    class MovementType(models.TextChoices):
        PURCHASE = 'purchase', 'Purchase / Restock'
        CONSUMPTION = 'consumption', 'Sales / Recipe Consumption'
        WASTE = 'waste', 'Waste / Spoilage'
        ADJUSTMENT = 'adjustment', 'Inventory Count Adjustment'
        RETURN = 'return', 'Return to Supplier'

    inventory_item = models.ForeignKey(
        InventoryItem,
        related_name='movements',
        on_delete=models.CASCADE
    )
    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices,
        default=MovementType.CONSUMPTION
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        help_text="Signed quantity delta in inventory units (+ for addition, - for deduction)"
    )
    previous_stock = models.DecimalField(max_digits=12, decimal_places=3)
    new_stock = models.DecimalField(max_digits=12, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Reference identifier (e.g. Order ORD-20261114-XYZ, Invoice #102)"
    )
    order = models.ForeignKey(
        'orders.Order',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='inventory_movements'
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='inventory_actions'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Stock Movement'
        verbose_name_plural = 'Stock Movements'

    def __str__(self):
        sign = "+" if self.quantity > 0 else ""
        return f"{self.get_movement_type_display()}: {sign}{self.quantity} {self.inventory_item.unit} of {self.inventory_item.name} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
