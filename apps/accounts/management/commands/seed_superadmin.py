from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from apps.accounts.constants import DEFAULT_ROLE_PERMISSIONS, PERMISSIONS
from apps.accounts.models import RolePermissionConfig

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds or initializes the Master Super Admin (Whole Admin Manager) for Amber Spice.'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='superadmin', help='Super admin username')
        parser.add_argument('--email', type=str, default='superadmin@amberspice.com', help='Super admin email')
        parser.add_argument('--password', type=str, default='SuperAdmin@2026!', help='Super admin password')

    def handle(self, *args, **options):
        username = options['username'].strip()
        email = options['email'].strip()
        password = options['password']

        self.stdout.write(self.style.NOTICE(f'Configuring Super Admin: {username} ({email})...'))

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'first_name': 'Amber Spice',
                'last_name': 'Super Admin',
                'role': User.Role.SUPER_ADMIN,
                'is_staff': True,
                'is_superuser': True,
            }
        )

        user.email = email
        user.first_name = 'Amber Spice'
        user.last_name = 'Super Admin'
        user.role = User.Role.SUPER_ADMIN
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        # Seed Super Admin Role Permission Config
        RolePermissionConfig.objects.get_or_create(
            role='super_admin',
            defaults={
                'name': 'Super Admin (Whole Admin Manager)',
                'description': 'Master administrative authority over all restaurant modules, staff accounts, branches, and system settings.',
                'permissions': list(PERMISSIONS.keys()),
                'is_customizable': False,
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'Successfully created Super Admin: {username} / {password}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Successfully updated Super Admin: {username} / {password}'))
