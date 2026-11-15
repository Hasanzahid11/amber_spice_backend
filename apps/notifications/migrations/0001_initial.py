import uuid
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
            name='Notification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('recipient_email', models.EmailField(blank=True, max_length=254)),
                ('recipient_phone', models.CharField(blank=True, max_length=30)),
                ('recipient_role', models.CharField(blank=True, help_text='e.g. customer, admin, manager, kitchen, delivery', max_length=30)),
                ('notification_type', models.CharField(choices=[('new_order', 'New Order Placed'), ('order_accepted', 'Order Accepted'), ('order_preparing', 'Order Preparing'), ('order_ready', 'Order Ready'), ('order_dispatched', 'Order Dispatched'), ('order_completed', 'Order Completed'), ('order_cancelled', 'Order Cancelled'), ('payment_confirmation', 'Payment Confirmation'), ('payment_failed', 'Payment Failed'), ('low_inventory', 'Low Inventory Alert'), ('admin_alert', 'Important Admin Alert')], db_index=True, max_length=40)),
                ('channel', models.CharField(choices=[('in_app', 'In-App / Dashboard'), ('email', 'Email'), ('sms', 'SMS Text'), ('whatsapp', 'WhatsApp'), ('push', 'Push Notification')], default='in_app', max_length=20)),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('data', models.JSONField(blank=True, default=dict, help_text='Metadata payload (e.g. order_id, order_number, total, action_url)')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('sent', 'Sent'), ('delivered', 'Delivered'), ('failed', 'Failed'), ('read', 'Read')], db_index=True, default='pending', max_length=20)),
                ('error_message', models.TextField(blank=True, help_text='Error log if delivery failed')),
                ('is_read', models.BooleanField(db_index=True, default=False)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('recipient', models.ForeignKey(blank=True, help_text='Target user (or null for guest / external recipient)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Notification',
                'verbose_name_plural': 'Notifications',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='NotificationPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email_enabled', models.BooleanField(default=True)),
                ('sms_enabled', models.BooleanField(default=True)),
                ('whatsapp_enabled', models.BooleanField(default=True)),
                ('push_enabled', models.BooleanField(default=True)),
                ('order_updates', models.BooleanField(default=True, help_text='Updates regarding order status changes')),
                ('promotional_updates', models.BooleanField(default=True, help_text='Discounts, coupons, and seasonal offers')),
                ('inventory_alerts', models.BooleanField(default=True, help_text='Staff only: alerts when ingredients run low')),
                ('admin_alerts', models.BooleanField(default=True, help_text='Staff only: urgent system and operational notices')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='notification_preferences', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Notification Preference',
                'verbose_name_plural': 'Notification Preferences',
            },
        ),
        migrations.CreateModel(
            name='NotificationTemplate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('event_type', models.CharField(choices=[('new_order', 'New Order Placed'), ('order_accepted', 'Order Accepted'), ('order_preparing', 'Order Preparing'), ('order_ready', 'Order Ready'), ('order_dispatched', 'Order Dispatched'), ('order_completed', 'Order Completed'), ('order_cancelled', 'Order Cancelled'), ('payment_confirmation', 'Payment Confirmation'), ('payment_failed', 'Payment Failed'), ('low_inventory', 'Low Inventory Alert'), ('admin_alert', 'Important Admin Alert')], help_text='Event triggering this template', max_length=40)),
                ('channel', models.CharField(choices=[('in_app', 'In-App / Dashboard'), ('email', 'Email'), ('sms', 'SMS Text'), ('whatsapp', 'WhatsApp'), ('push', 'Push Notification')], default='in_app', max_length=20)),
                ('title_template', models.CharField(help_text="e.g. 'Order #{order_number} is being prepared!'", max_length=200)),
                ('body_template', models.TextField(help_text="e.g. 'Hi {customer_name}, our chefs have begun preparing your order #{order_number}.'")),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Notification Template',
                'verbose_name_plural': 'Notification Templates',
                'ordering': ['event_type', 'channel'],
                'unique_together': {('event_type', 'channel')},
            },
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['recipient', 'is_read'], name='notificatio_recipie_411132_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['notification_type', 'created_at'], name='notificatio_notific_9d09c3_idx'),
        ),
    ]

