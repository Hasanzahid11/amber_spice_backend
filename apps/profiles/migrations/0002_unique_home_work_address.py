from django.db import migrations, models


def preserve_duplicate_addresses(apps, schema_editor):
    address_model = apps.get_model('profiles', 'UserAddress')
    seen = set()
    addresses = address_model.objects.using(schema_editor.connection.alias).filter(
        label__in=['home', 'work'],
    ).order_by('user_id', 'label', '-is_default', '-created_at', '-id')
    for address in addresses.iterator():
        slot = (address.user_id, address.label)
        if slot in seen:
            address_model.objects.using(schema_editor.connection.alias).filter(pk=address.pk).update(label='other')
        seen.add(slot)


class Migration(migrations.Migration):
    dependencies = [('profiles', '0001_initial')]
    operations = [
        migrations.RunPython(preserve_duplicate_addresses, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='useraddress',
            constraint=models.UniqueConstraint(
                fields=('user', 'label'), condition=models.Q(label__in=['home', 'work']),
                name='unique_home_work_address_per_user',
            ),
        ),
    ]
