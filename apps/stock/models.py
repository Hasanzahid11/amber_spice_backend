import uuid
from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class PurchaseOrder(models.Model):
    """
    Purchase Order issued to suppliers for replenishing restaurant ingredients and supplies.
    Supports tracking from draft/sent through partial and complete delivery receipt.
    """
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        ORDERED = 'ordered', 'Ordered / Sent to Supplier'
        PARTIALLY_RECEIVED = 'partially_received', 'Partially Received'
        RECEIVED = 'received', 'Fully Received / Delivered'
        CANCELLED = 'cancelled', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    po_number = models.CharField(max_length=50, unique=True, db_index=True)
    supplier = models.ForeignKey(
        'inventory.Supplier',
        on_delete=models.CASCADE,
        related_name='purchase_orders',
        help_text="Target vendor for this order"
    )
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.DRAFT)
    order_date = models.DateField(default=timezone.now)
    expected_delivery_date = models.DateField(null=True, blank=True)
    actual_delivery_date = models.DateField(null=True, blank=True)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    invoice_number = models.CharField(max_length=100, blank=True, help_text="Supplier invoice reference upon delivery")
    notes = models.TextField(blank=True, help_text="Special instructions or delivery notes")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_purchase_orders'
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='received_purchase_orders'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-order_date', '-created_at']
        verbose_name = 'Purchase Order'
        verbose_name_plural = 'Purchase Orders'

    def save(self, *args, **kwargs):
        if not self.po_number:
            date_str = timezone.now().strftime('%Y%m%d')
            rand_suffix = uuid.uuid4().hex[:4].upper()
            self.po_number = f"PO-{date_str}-{rand_suffix}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.po_number} - {self.supplier.name} (€{self.total_cost}) [{self.get_status_display()}]"

    def recalculate_totals(self):
        sub = sum((item.total_cost for item in self.items.all()), Decimal('0.00'))
        self.subtotal = sub
        self.total_cost = sub + self.tax
        self.save(update_fields=['subtotal', 'total_cost', 'updated_at'])


class PurchaseOrderItem(models.Model):
    """
    Individual line item in a Purchase Order.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='items'
    )
    inventory_item = models.ForeignKey(
        'inventory.InventoryItem',
        on_delete=models.CASCADE,
        related_name='po_items'
    )
    quantity_ordered = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))]
    )
    quantity_received = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal('0.000')
    )
    unit = models.CharField(max_length=30)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    batch_number = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    is_fully_received = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Purchase Order Item'
        verbose_name_plural = 'Purchase Order Items'

    def save(self, *args, **kwargs):
        if not self.unit and self.inventory_item:
            self.unit = self.inventory_item.unit
        if not self.unit_cost and self.inventory_item:
            self.unit_cost = self.inventory_item.purchase_price
        self.total_cost = (self.quantity_ordered * self.unit_cost).quantize(Decimal('0.01'))
        if self.quantity_received >= self.quantity_ordered:
            self.is_fully_received = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity_ordered} {self.unit} {self.inventory_item.name} for {self.purchase_order.po_number}"


class StockWastage(models.Model):
    """
    Detailed audit recording of damaged, spoiled, expired, or preparation wastage.
    Automatically decrements on-hand inventory stock.
    """
    class Reason(models.TextChoices):
        EXPIRED = 'expired', 'Expired / Past Best-Before'
        SPOILED = 'spoiled', 'Spoiled / Quality Degradation'
        DAMAGED = 'damaged', 'Damaged in Delivery / Storage'
        PREPARATION_WASTE = 'preparation_waste', 'Over-Prep / Cooking Burn / Kitchen Waste'
        SPILLAGE = 'spillage', 'Spillage / Accident'
        OTHER = 'other', 'Other Reason'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventory_item = models.ForeignKey(
        'inventory.InventoryItem',
        on_delete=models.CASCADE,
        related_name='wastage_logs'
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))]
    )
    unit = models.CharField(max_length=30)
    cost_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_waste_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    reason = models.CharField(max_length=30, choices=Reason.choices, default=Reason.SPOILED)
    notes = models.TextField(blank=True, help_text="Explanation or circumstances of the loss")

    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='logged_wastage'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Stock Wastage'
        verbose_name_plural = 'Stock Wastage Records'

    def save(self, *args, **kwargs):
        if not self.cost_per_unit and self.inventory_item:
            self.cost_per_unit = self.inventory_item.purchase_price
        self.total_waste_cost = (self.quantity * self.cost_per_unit).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} {self.unit} {self.inventory_item.name} wasted (€{self.total_waste_cost}) - {self.get_reason_display()}"


class StockTransfer(models.Model):
    """
    Transfers inventory between storage locations (e.g. Bulk Walk-in Cooler -> Kitchen Line, Dry Store -> Curry Station).
    """
    class Status(models.TextChoices):
        COMPLETED = 'completed', 'Completed'
        PENDING = 'pending', 'Pending'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer_number = models.CharField(max_length=50, unique=True, db_index=True)
    from_location = models.CharField(max_length=100, help_text="Source storage (e.g. Walk-in Cooler)")
    to_location = models.CharField(max_length=100, help_text="Destination (e.g. Line 1 Prep Table)")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETED)
    notes = models.TextField(blank=True)

    transferred_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='stock_transfers'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Stock Transfer'
        verbose_name_plural = 'Stock Transfers'

    def save(self, *args, **kwargs):
        if not self.transfer_number:
            date_str = timezone.now().strftime('%Y%m%d')
            rand_suffix = uuid.uuid4().hex[:4].upper()
            self.transfer_number = f"TRF-{date_str}-{rand_suffix}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.transfer_number}: {self.from_location} -> {self.to_location}"


class StockTransferItem(models.Model):
    """
    Line item inside a Stock Transfer.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer = models.ForeignKey(
        StockTransfer,
        on_delete=models.CASCADE,
        related_name='items'
    )
    inventory_item = models.ForeignKey(
        'inventory.InventoryItem',
        on_delete=models.CASCADE,
        related_name='transfer_items'
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))]
    )
    unit = models.CharField(max_length=30)

    class Meta:
        verbose_name = 'Stock Transfer Item'
        verbose_name_plural = 'Stock Transfer Items'

    def __str__(self):
        return f"{self.quantity} {self.unit} {self.inventory_item.name}"


class StockAuditCount(models.Model):
    """
    Physical stock count session / manual inventory audit.
    Compares physical on-hand counts against system expected stock,
    calculates discrepancies, and allows 1-click stock reconciliation.
    """
    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'Count In Progress'
        RECONCILED = 'reconciled', 'Reconciled / Stock Updated'
        CANCELLED = 'cancelled', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    audit_number = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=150, help_text="Audit label (e.g. Weekly Monday Count, Month-End Audit)")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    audit_date = models.DateField(default=timezone.now)

    total_expected_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_actual_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_variance_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='stock_audits'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reconciled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-audit_date', '-created_at']
        verbose_name = 'Stock Audit Count'
        verbose_name_plural = 'Stock Audit Counts'

    def save(self, *args, **kwargs):
        if not self.audit_number:
            date_str = timezone.now().strftime('%Y%m%d')
            rand_suffix = uuid.uuid4().hex[:4].upper()
            self.audit_number = f"AUD-{date_str}-{rand_suffix}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.audit_number} - {self.name} [{self.get_status_display()}]"

    def calculate_totals(self):
        exp_val = Decimal('0.00')
        act_val = Decimal('0.00')
        var_val = Decimal('0.00')

        for item in self.items.all():
            exp_val += item.expected_stock * item.unit_cost
            act_val += item.actual_stock * item.unit_cost
            var_val += item.variance_cost

        self.total_expected_value = exp_val.quantize(Decimal('0.01'))
        self.total_actual_value = act_val.quantize(Decimal('0.01'))
        self.total_variance_value = var_val.quantize(Decimal('0.01'))
        self.save(update_fields=['total_expected_value', 'total_actual_value', 'total_variance_value'])


class StockAuditItem(models.Model):
    """
    Single counted item in a Stock Audit session.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    audit = models.ForeignKey(
        StockAuditCount,
        on_delete=models.CASCADE,
        related_name='items'
    )
    inventory_item = models.ForeignKey(
        'inventory.InventoryItem',
        on_delete=models.CASCADE,
        related_name='audit_items'
    )
    expected_stock = models.DecimalField(max_digits=12, decimal_places=3)
    actual_stock = models.DecimalField(max_digits=12, decimal_places=3)
    variance = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'))
    unit = models.CharField(max_length=30)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    variance_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = 'Stock Audit Item'
        verbose_name_plural = 'Stock Audit Items'

    def save(self, *args, **kwargs):
        if not self.unit and self.inventory_item:
            self.unit = self.inventory_item.unit
        if not self.unit_cost and self.inventory_item:
            self.unit_cost = self.inventory_item.purchase_price
        self.variance = self.actual_stock - self.expected_stock
        self.variance_cost = (self.variance * self.unit_cost).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.inventory_item.name}: Expected {self.expected_stock}, Actual {self.actual_stock} (Var: {self.variance})"

