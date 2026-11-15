import uuid
from decimal import Decimal
from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('inventory', '0002_supplier_recipe_stockmovement_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PurchaseOrder',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('po_number', models.CharField(db_index=True, max_length=50, unique=True)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('ordered', 'Ordered / Sent to Supplier'), ('partially_received', 'Partially Received'), ('received', 'Fully Received / Delivered'), ('cancelled', 'Cancelled')], default='draft', max_length=25)),
                ('order_date', models.DateField(default=django.utils.timezone.now)),
                ('expected_delivery_date', models.DateField(blank=True, null=True)),
                ('actual_delivery_date', models.DateField(blank=True, null=True)),
                ('subtotal', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('tax', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('total_cost', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('invoice_number', models.CharField(blank=True, help_text='Supplier invoice reference upon delivery', max_length=100)),
                ('notes', models.TextField(blank=True, help_text='Special instructions or delivery notes')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_purchase_orders', to=settings.AUTH_USER_MODEL)),
                ('received_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='received_purchase_orders', to=settings.AUTH_USER_MODEL)),
                ('supplier', models.ForeignKey(help_text='Target vendor for this order', on_delete=django.db.models.deletion.CASCADE, related_name='purchase_orders', to='inventory.supplier')),
            ],
            options={
                'verbose_name': 'Purchase Order',
                'verbose_name_plural': 'Purchase Orders',
                'ordering': ['-order_date', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='StockAuditCount',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('audit_number', models.CharField(db_index=True, max_length=50, unique=True)),
                ('name', models.CharField(help_text='Audit label (e.g. Weekly Monday Count, Month-End Audit)', max_length=150)),
                ('status', models.CharField(choices=[('in_progress', 'Count In Progress'), ('reconciled', 'Reconciled / Stock Updated'), ('cancelled', 'Cancelled')], default='in_progress', max_length=20)),
                ('audit_date', models.DateField(default=django.utils.timezone.now)),
                ('total_expected_value', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('total_actual_value', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('total_variance_value', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reconciled_at', models.DateTimeField(blank=True, null=True)),
                ('performed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stock_audits', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Stock Audit Count',
                'verbose_name_plural': 'Stock Audit Counts',
                'ordering': ['-audit_date', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='StockTransfer',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('transfer_number', models.CharField(db_index=True, max_length=50, unique=True)),
                ('from_location', models.CharField(help_text='Source storage (e.g. Walk-in Cooler)', max_length=100)),
                ('to_location', models.CharField(help_text='Destination (e.g. Line 1 Prep Table)', max_length=100)),
                ('status', models.CharField(choices=[('completed', 'Completed'), ('pending', 'Pending')], default='completed', max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('transferred_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stock_transfers', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Stock Transfer',
                'verbose_name_plural': 'Stock Transfers',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='StockWastage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('quantity', models.DecimalField(decimal_places=3, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.001'))])),
                ('unit', models.CharField(max_length=30)),
                ('cost_per_unit', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('total_waste_cost', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('reason', models.CharField(choices=[('expired', 'Expired / Past Best-Before'), ('spoiled', 'Spoiled / Quality Degradation'), ('damaged', 'Damaged in Delivery / Storage'), ('preparation_waste', 'Over-Prep / Cooking Burn / Kitchen Waste'), ('spillage', 'Spillage / Accident'), ('other', 'Other Reason')], default='spoiled', max_length=30)),
                ('notes', models.TextField(blank=True, help_text='Explanation or circumstances of the loss')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('inventory_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wastage_logs', to='inventory.inventoryitem')),
                ('logged_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='logged_wastage', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Stock Wastage',
                'verbose_name_plural': 'Stock Wastage Records',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='StockTransferItem',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('quantity', models.DecimalField(decimal_places=3, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.001'))])),
                ('unit', models.CharField(max_length=30)),
                ('inventory_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transfer_items', to='inventory.inventoryitem')),
                ('transfer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='stock.stocktransfer')),
            ],
            options={
                'verbose_name': 'Stock Transfer Item',
                'verbose_name_plural': 'Stock Transfer Items',
            },
        ),
        migrations.CreateModel(
            name='StockAuditItem',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('expected_stock', models.DecimalField(decimal_places=3, max_digits=12)),
                ('actual_stock', models.DecimalField(decimal_places=3, max_digits=12)),
                ('variance', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=12)),
                ('unit', models.CharField(max_length=30)),
                ('unit_cost', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('variance_cost', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('notes', models.CharField(blank=True, max_length=200)),
                ('audit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='stock.stockauditcount')),
                ('inventory_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audit_items', to='inventory.inventoryitem')),
            ],
            options={
                'verbose_name': 'Stock Audit Item',
                'verbose_name_plural': 'Stock Audit Items',
            },
        ),
        migrations.CreateModel(
            name='PurchaseOrderItem',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('quantity_ordered', models.DecimalField(decimal_places=3, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.001'))])),
                ('quantity_received', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=12)),
                ('unit', models.CharField(max_length=30)),
                ('unit_cost', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('total_cost', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('batch_number', models.CharField(blank=True, max_length=100)),
                ('expiry_date', models.DateField(blank=True, null=True)),
                ('is_fully_received', models.BooleanField(default=False)),
                ('inventory_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='po_items', to='inventory.inventoryitem')),
                ('purchase_order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='stock.purchaseorder')),
            ],
            options={
                'verbose_name': 'Purchase Order Item',
                'verbose_name_plural': 'Purchase Order Items',
            },
        ),
    ]

