import uuid
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DailySalesSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(db_index=True, unique=True)),
                ('total_sales', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('order_count', models.PositiveIntegerField(default=0)),
                ('average_order_value', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('delivery_sales', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('delivery_orders_count', models.PositiveIntegerField(default=0)),
                ('collection_sales', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('collection_orders_count', models.PositiveIntegerField(default=0)),
                ('dine_in_sales', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('dine_in_orders_count', models.PositiveIntegerField(default=0)),
                ('food_cost', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('estimated_gross_margin', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('gross_margin_percentage', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=5)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Daily Sales Snapshot',
                'verbose_name_plural': 'Daily Sales Snapshots',
                'ordering': ['-date'],
            },
        ),
        migrations.CreateModel(
            name='ReportExportLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('report_type', models.CharField(help_text='e.g. sales_summary, sales_by_product, daily_sales', max_length=60)),
                ('export_format', models.CharField(choices=[('csv', 'CSV (.csv)'), ('excel', 'Excel Spreadsheet'), ('pdf', 'PDF Document'), ('html', 'HTML Print View')], default='csv', max_length=20)),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('row_count', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('generated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='report_exports', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Report Export Log',
                'verbose_name_plural': 'Report Export Logs',
                'ordering': ['-created_at'],
            },
        ),
    ]

