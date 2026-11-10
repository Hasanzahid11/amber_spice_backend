import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from .constants import DEFAULT_ROLE_PERMISSIONS, PERMISSIONS


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


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = 'super_admin', 'Super Admin'
        MANAGER = 'manager', 'Manager (Super Admin)'
        ADMIN = 'admin', 'Owner/Admin'
        STAFF = 'staff', 'Operations Staff'
        CHEF = 'chef', 'Chef (Kitchen)'
        KITCHEN_STAFF = 'kitchen_staff', 'Kitchen Staff'
        DELIVERY_STAFF = 'delivery_staff', 'Delivery Staff'
        CASHIER_FRONT = 'cashier_front', 'Cashier/Front Staff'
        CUSTOMER = 'customer', 'Customer'

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    email = models.EmailField(unique=True, help_text='Required. Unique email address.')
    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.CUSTOMER,
        help_text='Designates staff or customer role in the restaurant system.'
    )
    phone = models.CharField(max_length=30, blank=True, null=True)
    avatar = models.URLField(max_length=500, blank=True, null=True)
    is_vip = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_joined']
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_super_admin(self) -> bool:
        """Manager / Super Admin has overarching master authority across all modules, staff, and settings."""
        return self.is_superuser or self.role in [self.Role.SUPER_ADMIN, self.Role.MANAGER, self.Role.ADMIN]

    @property
    def is_owner_or_admin(self) -> bool:
        return self.is_super_admin

    @property
    def is_manager(self) -> bool:
        return self.is_super_admin

    @property
    def is_chef(self) -> bool:
        return self.role in [self.Role.CHEF, self.Role.KITCHEN_STAFF]

    @property
    def is_kitchen_staff(self) -> bool:
        return self.is_chef

    @property
    def is_operations_staff(self) -> bool:
        return self.role in [self.Role.STAFF, self.Role.CASHIER_FRONT]

    @property
    def is_delivery_staff(self) -> bool:
        return self.role == self.Role.DELIVERY_STAFF

    @property
    def is_cashier_or_front(self) -> bool:
        return self.role == self.Role.CASHIER_FRONT

    @property
    def is_restaurant_staff(self) -> bool:
        return self.role in [
            self.Role.SUPER_ADMIN,
            self.Role.MANAGER,
            self.Role.ADMIN,
            self.Role.STAFF,
            self.Role.CHEF,
            self.Role.KITCHEN_STAFF,
            self.Role.DELIVERY_STAFF,
            self.Role.CASHIER_FRONT,
        ] or self.is_staff or self.is_superuser

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
