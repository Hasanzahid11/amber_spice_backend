import re
from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from .constants import (
    DEFAULT_ROLE_PERMISSIONS,
    PERMISSIONS,
    ROLE_DESCRIPTIONS,
    ROLE_DISPLAY_NAMES,
)


class CustomUserManager(UserManager):
    """
    Custom user manager that handles optional email / primary phone,
    auto-generates username if not supplied, and normalizes empty strings to None.
    """
    def create_user(self, username=None, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)

        if email == "":
            email = None
        if extra_fields.get('phone') == "":
            extra_fields['phone'] = None

        if not username:
            phone = extra_fields.get('phone')
            if phone:
                base = re.sub(r'[^\w+_-]', '', str(phone))
            elif email:
                base = email.split('@')[0]
            else:
                base = 'user'
            username = base
            counter = 1
            while self.model.objects.filter(username=username).exists():
                username = f"{base}_{counter}"
                counter += 1

        return super().create_user(username=username, email=email, password=password, **extra_fields)

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        if email == "":
            email = None
        return super().create_superuser(username=username, email=email, password=password, **extra_fields)


class RolePermissionConfig(models.Model):
    """
    Configurable permissions for each role.
    Allows Owner/Admin to adjust permissions per role at runtime.
    """
    role = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    permissions = models.JSONField(default=list, help_text="List of permission code strings")
    is_customizable = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['role']
        verbose_name = 'Role Permission Configuration'
        verbose_name_plural = 'Role Permission Configurations'

    def __str__(self):
        return f"{self.name} ({len(self.permissions)} permissions)"

    @classmethod
    def get_role_permissions(cls, role: str) -> list[str]:
        config = cls.objects.filter(role=role).first()
        if config:
            return config.permissions
        return DEFAULT_ROLE_PERMISSIONS.get(role, [])

    @classmethod
    def ensure_defaults(cls):
        """
        Guarantees that all standard restaurant roles have a database-backed
        configuration record. If missing, it creates the record with defaults.
        """
        for role_key, perms in DEFAULT_ROLE_PERMISSIONS.items():
            cls.objects.get_or_create(
                role=role_key,
                defaults={
                    'name': ROLE_DISPLAY_NAMES.get(role_key, role_key.replace('_', ' ').title()),
                    'description': ROLE_DESCRIPTIONS.get(role_key, ''),
                    'permissions': perms,
                    'is_customizable': role_key != 'admin',
                }
            )

    def reset_to_default(self) -> list[str]:
        """Resets this role's permissions back to the initial system defaults."""
        self.permissions = list(DEFAULT_ROLE_PERMISSIONS.get(self.role, []))
        self.save()
        return self.permissions


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Owner/Admin'
        MANAGER = 'manager', 'Manager'
        KITCHEN_STAFF = 'kitchen_staff', 'Kitchen Staff'
        DELIVERY_STAFF = 'delivery_staff', 'Delivery Staff'
        CASHIER_FRONT = 'cashier_front', 'Cashier/Front Staff'
        CUSTOMER = 'customer', 'Customer'

    email = models.EmailField(
        blank=True,
        null=True,
        unique=True,
        help_text='Unique email address (optional if phone is provided).'
    )
    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.CUSTOMER,
        help_text='Designates staff or customer role in the restaurant system.'
    )
    phone = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        unique=True,
        help_text='Primary contact number (optional if email is provided).'
    )
    avatar = models.URLField(max_length=500, blank=True, null=True)
    is_vip = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta:
        ordering = ['-date_joined']
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def clean(self):
        super().clean()
        if self.email == "":
            self.email = None
        if self.phone == "":
            self.phone = None

    def save(self, *args, **kwargs):
        if self.email == "":
            self.email = None
        if self.phone == "":
            self.phone = None
        super().save(*args, **kwargs)

    def __str__(self):
        display_name = self.get_full_name() or self.username or self.phone or self.email or f"User #{self.id}"
        return f"{display_name} ({self.get_role_display()})"

    @property
    def is_owner_or_admin(self) -> bool:
        return self.is_superuser or self.role == self.Role.ADMIN

    @property
    def is_manager(self) -> bool:
        return self.role == self.Role.MANAGER

    @property
    def is_kitchen_staff(self) -> bool:
        return self.role == self.Role.KITCHEN_STAFF

    @property
    def is_delivery_staff(self) -> bool:
        return self.role == self.Role.DELIVERY_STAFF

    @property
    def is_cashier_or_front(self) -> bool:
        return self.role == self.Role.CASHIER_FRONT

    @property
    def is_customer(self) -> bool:
        return self.role == self.Role.CUSTOMER

    @property
    def is_restaurant_staff(self) -> bool:
        return self.role in [
            self.Role.ADMIN,
            self.Role.MANAGER,
            self.Role.KITCHEN_STAFF,
            self.Role.DELIVERY_STAFF,
            self.Role.CASHIER_FRONT,
        ] or self.is_staff

    def has_restaurant_permission(self, perm_code: str) -> bool:
        """
        Evaluates whether the user has the given permission:
        1. Owner/Admin and superusers always have full access.
        2. Explicit user-level revocations take precedence.
        3. Explicit user-level grants take precedence.
        4. Configurable role-level permissions are checked.
        """
        if self.is_owner_or_admin:
            return True

        # Check user-level overrides
        custom = getattr(self, 'custom_permissions', None)
        if custom:
            if perm_code in custom.revoked_permissions:
                return False
            if perm_code in custom.granted_permissions:
                return True

        # Check role-level configuration
        role_perms = RolePermissionConfig.get_role_permissions(self.role)
        return perm_code in role_perms

    @property
    def all_permissions(self) -> list[str]:
        """
        Returns full consolidated list of effective permissions for this user.
        """
        if self.is_owner_or_admin:
            return list(PERMISSIONS.keys())

        perms = set(RolePermissionConfig.get_role_permissions(self.role))

        custom = getattr(self, 'custom_permissions', None)
        if custom:
            perms.update(custom.granted_permissions)
            perms.difference_update(custom.revoked_permissions)

        return sorted(list(perms))


class UserCustomPermission(models.Model):
    """
    Optional user-level overrides to grant or revoke specific permissions.
    """
    user = models.OneToOneField(
        User,
        related_name='custom_permissions',
        on_delete=models.CASCADE
    )
    granted_permissions = models.JSONField(
        default=list,
        help_text="Extra permissions granted specifically to this user"
    )
    revoked_permissions = models.JSONField(
        default=list,
        help_text="Permissions specifically revoked from this user"
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Custom perms for {self.user.username}"
