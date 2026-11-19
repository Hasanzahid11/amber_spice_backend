import uuid
from django.db import migrations, models


def initialize_contact_credentials(apps, schema_editor):
    order_model = apps.get_model('orders', 'Order')
    alias = schema_editor.connection.alias
    for pk in order_model.objects.using(alias).filter(customer_chat_token__isnull=True).values_list('pk', flat=True).iterator():
        order_model.objects.using(alias).filter(pk=pk).update(customer_chat_token=uuid.uuid4())


class Migration(migrations.Migration):
    dependencies = [('orders', '0009_kitchen_handover_delivery_chat')]
    operations = [
        migrations.RunPython(initialize_contact_credentials, migrations.RunPython.noop),
        migrations.AlterField(model_name='order', name='customer_chat_token', field=models.UUIDField(default=uuid.uuid4, editable=False)),
    ]
