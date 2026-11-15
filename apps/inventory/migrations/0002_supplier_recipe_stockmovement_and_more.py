from decimal import Decimal
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('menu', '0001_initial'),
        ('orders', '0001_initial'),
        ('inventory', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Supplier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, unique=True)),
                ('contact_name', models.CharField(blank=True, max_length=150)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('phone', models.CharField(blank=True, max_length=30)),
                ('address', models.TextField(blank=True)),
                ('lead_time_days', models.PositiveIntegerField(default=2, help_text='Delivery lead time in days')),
                ('payment_terms', models.CharField(blank=True, default='Net 30', max_length=100)),
                ('notes', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Supplier',
                'verbose_name_plural': 'Suppliers',
                'ordering': ['name'],
            },
        ),
        migrations.AlterModelOptions(
            name='inventoryitem',
            options={'ordering': ['name'], 'verbose_name': 'Inventory Item', 'verbose_name_plural': 'Inventory Items'},
        ),
        migrations.AddField(
            model_name='inventoryitem',
            name='batch_number',
            field=models.CharField(blank=True, help_text='Supplier lot / batch identification number', max_length=100),
        ),
        migrations.AddField(
            model_name='inventoryitem',
            name='expiry_date',
            field=models.DateField(blank=True, help_text='Current batch expiry date where relevant', null=True),
        ),
        migrations.AddField(
            model_name='inventoryitem',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='inventoryitem',
            name='purchase_price',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Cost price per primary unit (e.g. €/kg)', max_digits=10),
        ),
        migrations.AddField(
            model_name='inventoryitem',
            name='reorder_level',
            field=models.DecimalField(decimal_places=3, default=Decimal('0.000'), help_text='Stock level triggering automatic reorder recommendations', max_digits=12),
        ),
        migrations.AddField(
            model_name='inventoryitem',
            name='storage_location',
            field=models.CharField(blank=True, help_text='Storage location (e.g. Walk-in Cooler, Dry Shelf B, Freezer)', max_length=100),
        ),
        migrations.AddField(
            model_name='inventoryitem',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='inventoryitem',
            name='category',
            field=models.CharField(choices=[
                ('Meat & Poultry', 'Meat & Poultry (Chicken, etc.)'),
                ('Beef & Red Meat', 'Beef & Lamb'),
                ('Seafood', 'Seafood & Fish'),
                ('Rice & Grains', 'Rice & Grains'),
                ('Flour & Bakery', 'Flour & Bakery'),
                ('Oils & Fats', 'Cooking Oil & Fats'),
                ('Vegetables', 'Vegetables & Fresh Produce'),
                ('Sauces', 'Sauces, Pastes & Condiments'),
                ('Spices & Seasoning', 'Spices & Seasoning'),
                ('Dairy', 'Dairy (Paneer, Milk, Curd, Butter)'),
                ('Drinks', 'Drinks & Beverages'),
                ('Packaging Materials', 'Packaging & Takeaway Supplies'),
                ('Pantry', 'Pantry & Dry Goods'),
                ('Produce', 'Produce'),
                ('Other Supplies', 'Other Ingredients & Supplies'),
            ], max_length=100),
        ),
        migrations.AlterField(
            model_name='inventoryitem',
            name='current_stock',
            field=models.DecimalField(decimal_places=3, default=Decimal('0.000'), help_text='Current physical on-hand quantity', max_digits=12),
        ),
        migrations.AlterField(
            model_name='inventoryitem',
            name='minimum_stock',
            field=models.DecimalField(decimal_places=3, default=Decimal('0.000'), help_text='Safety stock threshold', max_digits=12),
        ),
        migrations.AlterField(
            model_name='inventoryitem',
            name='supplier',
            field=models.CharField(blank=True, help_text='Supplier or vendor name', max_length=200),
        ),
        migrations.AlterField(
            model_name='inventoryitem',
            name='unit',
            field=models.CharField(default='kg', help_text='Primary inventory unit (kg, g, litre, ml, pieces, etc.)', max_length=30),
        ),
        migrations.AddField(
            model_name='inventoryitem',
            name='supplier_ref',
            field=models.ForeignKey(blank=True, help_text='Linked supplier profile', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inventory_items', to='inventory.supplier'),
        ),
        migrations.CreateModel(
            name='Recipe',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=200)),
                ('yield_portions', models.PositiveIntegerField(default=1, help_text='Number of standard portions this recipe yields', validators=[django.core.validators.MinValueValidator(1)])),
                ('instructions', models.TextField(blank=True, help_text='Preparation / cooking notes for kitchen staff')),
                ('prep_time_minutes', models.PositiveIntegerField(default=15)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('dish', models.OneToOneField(help_text='The menu dish produced by this recipe', on_delete=django.db.models.deletion.CASCADE, related_name='recipe', to='menu.dish')),
            ],
            options={
                'verbose_name': 'Recipe / BOM',
                'verbose_name_plural': 'Recipes / BOMs',
                'ordering': ['dish__name'],
            },
        ),
        migrations.CreateModel(
            name='StockMovement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('movement_type', models.CharField(choices=[('purchase', 'Purchase / Restock'), ('consumption', 'Sales / Recipe Consumption'), ('waste', 'Waste / Spoilage'), ('adjustment', 'Inventory Count Adjustment'), ('return', 'Return to Supplier')], default='consumption', max_length=20)),
                ('quantity', models.DecimalField(decimal_places=3, help_text='Signed quantity delta in inventory units (+ for addition, - for deduction)', max_digits=12)),
                ('previous_stock', models.DecimalField(decimal_places=3, max_digits=12)),
                ('new_stock', models.DecimalField(decimal_places=3, max_digits=12)),
                ('unit_cost', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('total_cost', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('reference', models.CharField(blank=True, help_text='Reference identifier (e.g. Order ORD-20261114-XYZ, Invoice #102)', max_length=100)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('inventory_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='movements', to='inventory.inventoryitem')),
                ('order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inventory_movements', to='orders.order')),
                ('performed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inventory_actions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Stock Movement',
                'verbose_name_plural': 'Stock Movements',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='RecipeIngredient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=3, help_text='Quantity required for the recipe yield (e.g. 200 for 200g, 0.2 for 0.2kg)', max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0.001'))])),
                ('unit', models.CharField(help_text='Unit of measurement in recipe (e.g. g, kg, ml, litre, pieces)', max_length=30)),
                ('notes', models.CharField(blank=True, help_text='Prep details (e.g. diced, boneless, washed)', max_length=150)),
                ('inventory_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recipe_usages', to='inventory.inventoryitem')),
                ('recipe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ingredients', to='inventory.recipe')),
            ],
            options={
                'verbose_name': 'Recipe Ingredient',
                'verbose_name_plural': 'Recipe Ingredients',
                'ordering': ['inventory_item__name'],
                'unique_together': {('recipe', 'inventory_item')},
            },
        ),
    ]

