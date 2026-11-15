import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('orders', '0004_order_priority_order_prepared_at_order_ready_at_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='KitchenStation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Station name (e.g. Curry Station, Grill, Biryani)', max_length=100, unique=True)),
                ('slug', models.SlugField(blank=True, help_text='Station code matching dish station tags', max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('color_code', models.CharField(default='#E65100', help_text='Hex color code for KDS badge header (e.g. #D32F2F, #1976D2, #388E3C)', max_length=20)),
                ('display_order', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True, help_text='Active station receiving orders on KDS')),
                ('default_prep_time_minutes', models.PositiveIntegerField(default=15, help_text='Standard prep time baseline in minutes')),
                ('printer_ip', models.CharField(blank=True, help_text='Network ticket printer IP or identifier for this station', max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Kitchen Station',
                'verbose_name_plural': 'Kitchen Stations',
                'ordering': ['display_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='KitchenScreen',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Screen terminal label (e.g. Main Kitchen Pass, Curry Station 1)', max_length=100)),
                ('screen_type', models.CharField(choices=[('station', 'Station Screen (Station-Specific Items)'), ('expeditor', 'Expeditor / Pass Screen (All Order Items)'), ('runner', 'Food Runner Screen (Ready Pickups)'), ('customer_facing', 'Order Status Board (Customer Display)')], default='expeditor', help_text='Role and display behavior of this screen', max_length=20)),
                ('device_identifier', models.CharField(blank=True, help_text='Unique hardware ID, tablet serial, or browser fingerprint', max_length=100)),
                ('auto_refresh_seconds', models.PositiveIntegerField(default=10, help_text='KDS polling / refresh rate interval in seconds')),
                ('warning_threshold_pct', models.PositiveIntegerField(default=75, help_text='Percentage of target prep time elapsed before badge turns Yellow (Warning)')),
                ('critical_delay_minutes', models.PositiveIntegerField(default=10, help_text='Minutes overdue before badge flashes Red (Critical Delayed)')),
                ('sound_alerts_enabled', models.BooleanField(default=True, help_text='Play audio chime when new order arrives or order becomes critically delayed')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('station', models.ForeignKey(blank=True, help_text='Assign to a specific station to filter items (leave blank for all stations / expeditor)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='screens', to='kitchen.kitchenstation')),
            ],
            options={
                'verbose_name': 'Kitchen Screen',
                'verbose_name_plural': 'Kitchen Screens',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='KitchenBumpLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('action', models.CharField(choices=[('start_prep', 'Start Preparing (New -> Preparing)'), ('mark_ready', 'Mark Ready (Preparing -> Ready)'), ('recall', 'Recall Ticket (Ready -> Preparing)'), ('item_ready', 'Item Marked Ready'), ('item_unready', 'Item Reopened'), ('set_priority', 'Set Priority'), ('expedite', 'Expedited / Rush'), ('add_note', 'Kitchen Note Added')], max_length=30)),
                ('from_status', models.CharField(blank=True, max_length=30)),
                ('to_status', models.CharField(blank=True, max_length=30)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('item', models.ForeignKey(blank=True, help_text='Specific item if action is item-level', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='kitchen_logs', to='orders.orderitem')),
                ('order', models.ForeignKey(help_text='Target order on KDS', on_delete=django.db.models.deletion.CASCADE, related_name='kitchen_bump_logs', to='orders.order')),
                ('performed_by', models.ForeignKey(blank=True, help_text='Chef / Staff member who performed the action', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='kitchen_actions', to=settings.AUTH_USER_MODEL)),
                ('station', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='kitchen.kitchenstation')),
            ],
            options={
                'verbose_name': 'Kitchen Bump Log',
                'verbose_name_plural': 'Kitchen Bump Logs',
                'ordering': ['-created_at'],
            },
        ),
    ]

