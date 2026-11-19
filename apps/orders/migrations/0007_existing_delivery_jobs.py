from django.db import migrations


def backfill_delivery_jobs(apps, schema_editor):
    order_model = apps.get_model('orders', 'Order')
    event_model = apps.get_model('orders', 'OrderEvent')
    job_model = apps.get_model('orders', 'DeliveryJob')
    alias = schema_editor.connection.alias
    for order in order_model.objects.using(alias).filter(dining_type='delivery', assigned_delivery_staff__isnull=False).iterator():
        stage = {'out_for_delivery': 'picked_up', 'delivered': 'delivered', 'cancelled': 'cancelled'}.get(order.status, 'assigned')
        events = event_model.objects.using(alias).filter(order_id=order.id)
        pickup = events.filter(status='out_for_delivery').order_by('created_at').first()
        delivered = events.filter(status='delivered').order_by('created_at').first()
        job_model.objects.using(alias).get_or_create(order_id=order.id, defaults={
            'stage': stage, 'picked_up_at': pickup.created_at if pickup else None,
            'delivered_at': delivered.created_at if delivered else None,
        })


class Migration(migrations.Migration):
    dependencies = [('orders', '0006_rider_workspace')]
    operations = [migrations.RunPython(backfill_delivery_jobs, migrations.RunPython.noop)]
