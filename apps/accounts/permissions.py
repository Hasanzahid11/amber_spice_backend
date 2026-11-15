from rest_framework import permissions


class HasRestaurantPermission(permissions.BasePermission):
    """
    Dynamic permission checker.
    Usage in ViewSet:
        permission_classes = [HasRestaurantPermission]
        required_permission = 'menu:manage'
    Or dynamically instantiated.
    """
    required_permission = None

    def __init__(self, required_permission=None):
        if required_permission:
            self.required_permission = required_permission

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        perm = getattr(view, 'required_permission', self.required_permission)
        if not perm:
            return True

        return request.user.has_restaurant_permission(perm)


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Grants access exclusively to Owner/Admin or Django Superuser.
    """
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_owner_or_admin
        )


class IsManagerOrAdmin(permissions.BasePermission):
    """
    Grants access to Managers and Owner/Admins.
    """
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_owner_or_admin or request.user.is_manager)
        )


class IsRestaurantStaff(permissions.BasePermission):
    """
    Grants access to any restaurant staff member (Admin, Manager, Kitchen, Delivery, Cashier).
    """
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_restaurant_staff
        )


class CanManageOrders(permissions.BasePermission):
    """
    Orders & POS operations permission.
    Owner/Admin, Manager, Cashier/Front Staff.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_restaurant_permission('orders:update_status') or request.user.has_restaurant_permission('orders:view')


class CanAccessKitchenKDS(permissions.BasePermission):
    """
    Kitchen Staff, Manager, Owner/Admin.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_restaurant_permission('kitchen:view_orders')


class CanAccessDeliveries(permissions.BasePermission):
    """
    Delivery Staff, Manager, Owner/Admin.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_restaurant_permission('deliveries:view_assigned')


class CanManageMenu(permissions.BasePermission):
    """
    Manager, Owner/Admin.
    Allows safe methods (GET, HEAD, OPTIONS) for everyone.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.has_restaurant_permission('menu:manage')
        )


class CanToggleMenuAvailability(permissions.BasePermission):
    """
    Allows Kitchen Staff, Cashier, Manager, Admin to mark items available/unavailable.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_restaurant_permission('menu:toggle_availability')


class CanManageInventory(permissions.BasePermission):
    """
    Manager, Owner/Admin.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_restaurant_permission('inventory:manage')


class CanViewReports(permissions.BasePermission):
    """
    Reports & Financial analytics.
    Manager, Owner/Admin.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_restaurant_permission('reports:view')


class CanManageStaff(permissions.BasePermission):
    """
    Staff accounts & schedule management.
    Owner/Admin, Manager.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_restaurant_permission('staff:manage')


class CanManageReservations(permissions.BasePermission):
    """
    Cashier/Front, Manager, Owner/Admin.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_restaurant_permission('reservations:manage')


class IsSelfOrAdmin(permissions.BasePermission):
    """
    Allows user to access or edit their own profile, or Owner/Admin to edit any.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_owner_or_admin or obj == request.user


class CanViewCustomers(permissions.BasePermission):
    """
    Customer directory & VIP details access.
    Owner/Admin, Manager, Cashier/Front Staff.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_restaurant_permission('customers:view')


class CanAccessCustomerOperations(permissions.BasePermission):
    """
    Customer-facing operations (POS orders, reservations, customer directory).
    Cashier/Front Staff, Manager, Owner/Admin.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return (
            request.user.is_owner_or_admin
            or request.user.has_restaurant_permission('orders:create')
            or request.user.has_restaurant_permission('reservations:manage')
            or request.user.has_restaurant_permission('customers:view')
        )

