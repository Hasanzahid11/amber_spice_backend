from django.contrib import admin
from .models import DailySalesSnapshot, ReportExportLog


@admin.register(DailySalesSnapshot)
class DailySalesSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        'date',
        'total_sales',
        'order_count',
        'average_order_value',
        'delivery_sales',
        'collection_sales',
        'dine_in_sales',
        'food_cost',
        'estimated_gross_margin',
        'gross_margin_percentage',
    )
    list_filter = ('date',)
    date_hierarchy = 'date'
    ordering = ('-date',)


@admin.register(ReportExportLog)
class ReportExportLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'report_type',
        'export_format',
        'generated_by',
        'row_count',
        'start_date',
        'end_date',
    )
    list_filter = ('report_type', 'export_format', 'created_at')
    search_fields = ('report_type', 'generated_by__username')
    readonly_fields = (
        'id',
        'report_type',
        'export_format',
        'generated_by',
        'row_count',
        'start_date',
        'end_date',
        'created_at',
    )
