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
        ('menu', '0002_dish_available_ingredients_dish_available_modifiers'),
        ('orders', '0004_order_priority_order_prepared_at_order_ready_at_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Promotion',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Promotion name (e.g. Welcome 15% Off, Weekend Free Delivery)', max_length=150)),
                ('description', models.TextField(blank=True, help_text='Customer-facing description of terms and benefits')),
                ('code', models.CharField(blank=True, db_index=True, help_text='Coupon code (e.g. WELCOME15, FREEDELIVERY). Leave blank for automatic promotions.', max_length=50, null=True, unique=True)),
                ('discount_type', models.CharField(choices=[('percentage', 'Percentage Discount'), ('fixed_amount', 'Fixed Value Discount'), ('first_order', 'First Order Discount'), ('free_delivery', 'Free Delivery'), ('bogo', 'Buy One Get One (BOGO)')], default='percentage', max_length=30)),
                ('discount_value', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Percentage discount (e.g. 15.00 for 15%) or fixed discount amount (e.g. 5.00 for €5)', max_digits=10)),
                ('max_discount_amount', models.DecimalField(blank=True, decimal_places=2, help_text='Optional maximum discount cap for percentage discounts (e.g. 20% off up to max €15)', max_digits=10, null=True)),
                ('minimum_order_amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Minimum order subtotal required to qualify for this discount', max_digits=10)),
                ('applies_to', models.CharField(choices=[('entire_order', 'Entire Order'), ('specific_categories', 'Specific Menu Categories'), ('specific_dishes', 'Specific Dishes')], default='entire_order', max_length=30)),
                ('applicable_dining_types', models.JSONField(blank=True, default=list, help_text="Allowed dining types: ['delivery', 'takeaway', 'dine_in'] (leave empty for all)")),
                ('buy_quantity', models.PositiveIntegerField(default=1, help_text='Number of items customer must buy')),
                ('get_quantity', models.PositiveIntegerField(default=1, help_text='Number of reward items received')),
                ('get_discount_percentage', models.DecimalField(decimal_places=2, default=Decimal('100.00'), help_text='Discount percentage on the get_dish (100% = Free, 50% = Half Price)', max_digits=5, validators=[django.core.validators.MinValueValidator(Decimal('0.00')), django.core.validators.MaxValueValidator(Decimal('100.00'))])),
                ('start_date', models.DateTimeField(default=django.utils.timezone.now, help_text='When the promotion becomes active')),
                ('end_date', models.DateTimeField(blank=True, help_text='When the promotion expires', null=True)),
                ('has_time_window', models.BooleanField(default=False)),
                ('start_time', models.TimeField(blank=True, help_text='Start time of daily window', null=True)),
                ('end_time', models.TimeField(blank=True, help_text='End time of daily window', null=True)),
                ('days_of_week', models.JSONField(blank=True, default=list, help_text='Days of week (0=Mon, 6=Sun) where promotion is valid. Empty means all days.')),
                ('usage_limit_total', models.PositiveIntegerField(blank=True, help_text='Maximum total redemptions allowed across all customers (null = unlimited)', null=True)),
                ('usage_limit_per_customer', models.PositiveIntegerField(default=1, help_text='Maximum times an individual customer can use this promo')),
                ('times_used', models.PositiveIntegerField(default=0, help_text='Counter of total times redeemed')),
                ('is_first_order_only', models.BooleanField(default=False, help_text='Restricted exclusively to new customers placing their very first order')),
                ('is_active', models.BooleanField(default=True, help_text='Active toggle for admin to pause/resume')),
                ('is_featured', models.BooleanField(default=False, help_text='Featured on website homepage/cart')),
                ('banner_message', models.CharField(blank=True, help_text="Banner announcement text (e.g. 'Use code WEEKEND20 for 20% off orders over €40!')", max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('applicable_categories', models.ManyToManyField(blank=True, help_text="Categories eligible for this discount if applies_to is 'specific_categories'", related_name='promotions', to='menu.category')),
                ('applicable_dishes', models.ManyToManyField(blank=True, help_text="Dishes eligible for this discount if applies_to is 'specific_dishes'", related_name='promotions', to='menu.dish')),
                ('buy_dish', models.ForeignKey(blank=True, help_text='Dish required to buy for BOGO', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bogo_buy_promotions', to='menu.dish')),
                ('get_dish', models.ForeignKey(blank=True, help_text='Reward dish received in BOGO', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bogo_get_promotions', to='menu.dish')),
            ],
            options={
                'verbose_name': 'Promotion',
                'verbose_name_plural': 'Promotions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PromotionUsage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('customer_phone', models.CharField(blank=True, max_length=30)),
                ('customer_email', models.EmailField(blank=True, max_length=254)),
                ('discount_applied', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='promotion_usages', to='orders.order')),
                ('promotion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='usages', to='promotions.promotion')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='promotion_usages', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Promotion Usage',
                'verbose_name_plural': 'Promotion Usages',
                'ordering': ['-created_at'],
            },
        ),
    ]

