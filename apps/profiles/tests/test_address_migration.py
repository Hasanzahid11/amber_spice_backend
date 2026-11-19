from django.db import connection, IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class AddressSlotMigrationTests(TransactionTestCase):
    def test_duplicate_slots_preserve_records_as_other(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        previous = [('profiles', '0001_initial')]
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous).apps
            # Only profiles is rolled back; accounts retains its current UUID schema.
            current_apps = executor.loader.project_state(latest).apps
            user = current_apps.get_model('accounts', 'User').objects.create(username='migration_address_user')
            address_model = apps.get_model('profiles', 'UserAddress')
            home = address_model.objects.create(user_id=user.id, label='home', address_line1='Keep Home', postal_code='R93 KEEP', is_default=True)
            duplicate = address_model.objects.create(user_id=user.id, label='home', address_line1='Keep As Other', postal_code='R93 ALSO')
            MigrationExecutor(connection).migrate(latest)
            from apps.profiles.models import UserAddress
            self.assertEqual(UserAddress.objects.get(pk=home.pk).label, 'home')
            self.assertEqual(UserAddress.objects.get(pk=duplicate.pk).label, 'other')
            self.assertEqual(UserAddress.objects.get(pk=duplicate.pk).address_line1, 'Keep As Other')
            self.assertEqual(UserAddress.objects.filter(user_id=user.id).count(), 2)
            with self.assertRaises(IntegrityError), transaction.atomic():
                UserAddress.objects.create(user_id=user.id, label='home', address_line1='Duplicate Home', postal_code='R93 NOPE')
        finally:
            MigrationExecutor(connection).migrate(latest)
