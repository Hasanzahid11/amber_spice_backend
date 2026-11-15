from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_customeraddress_cart_cartitem_order_customer_email_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='priority',
            field=models.CharField(
                choices=[('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')],
                default='normal',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='prepared_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='ready_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='is_ready',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='prepared_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

