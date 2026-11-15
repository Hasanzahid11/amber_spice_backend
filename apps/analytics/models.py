import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models


class DailySalesSnapshot(models.Model):
    """
    Persisted daily sales and margin rollup for fast analytics querying and long-term trend analysis.
    """
    date = models.DateField(unique=True, db_index=True)
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    order_count = models.PositiveIntegerField(default=0)
    average_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Channel splits
    delivery_sales = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    delivery_orders_count = models.PositiveIntegerField(default=0)
    collection_sales = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    collection_orders_count = models.PositiveIntegerField(default=0)
    dine_in_sales = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    dine_in_orders_count = models.PositiveIntegerField(default=0)

    # Costing and Margins
    food_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    estimated_gross_margin = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    gross_margin_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Daily Sales Snapshot'
        verbose_name_plural = 'Daily Sales Snapshots'

    def __str__(self):
        return f"{self.date}: €{self.total_sales} ({self.order_count} orders)"


class ReportExportLog(models.Model):
    """
    Audit log recording exported financial, product, or sales reports.
    """
    class Format(models.TextChoices):
        CSV = 'csv', 'CSV (.csv)'
        EXCEL = 'excel', 'Excel Spreadsheet'
        PDF = 'pdf', 'PDF Document'
        HTML = 'html', 'HTML Print View'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report_type = models.CharField(max_length=60, help_text="e.g. sales_summary, sales_by_product, daily_sales")
    export_format = models.CharField(max_length=20, choices=Format.choices, default=Format.CSV)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='report_exports'
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Report Export Log'
        verbose_name_plural = 'Report Export Logs'

    def __str__(self):
        user_str = self.generated_by.username if self.generated_by else "System"
        return f"{self.get_export_format_display()} - {self.report_type} by {user_str} on {self.created_at.strftime('%Y-%m-%d %H:%M')}"
