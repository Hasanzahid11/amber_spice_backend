"""
Permission definitions and default role mappings for Restaurant Management.
Complies with Section 18: User Roles & Permissions.
"""

PERMISSIONS = {
    # Orders permissions
    'orders:view': 'Can view all orders',
    'orders:create': 'Can create new orders (cashier / front desk / phone)',
    'orders:update_status': 'Can update order status and payment status',
    'orders:cancel': 'Can cancel orders or process refunds',

    # Kitchen permissions
    'kitchen:view_orders': 'Can view kitchen orders on KDS',
    'kitchen:update_status': 'Can mark kitchen items preparing / ready',

    # Delivery permissions
    'deliveries:view_assigned': 'Can view assigned delivery orders',
    'deliveries:update_status': 'Can update delivery progress and mark delivered',

    # Menu permissions
    'menu:view': 'Can browse full menu and items',
    'menu:manage': 'Can create, edit, and delete dishes and categories',
    'menu:toggle_availability': 'Can mark menu items available or unavailable when out of stock',

    # Inventory permissions
    'inventory:view': 'Can view current inventory stock levels and status',
    'inventory:manage': 'Can add, edit, adjust stock, and restock inventory',

    # Reports and Analytics permissions
    'reports:view': 'Can view financial reports, sales analytics, and business summaries',

    # Staff permissions
    'staff:view': 'Can view staff list, schedules, and shift assignments',
    'staff:manage': 'Can add, edit, and manage staff accounts and shift schedules',

    # Reservations and Tables permissions
    'reservations:view': 'Can view table reservations and dining floor status',
    'reservations:manage': 'Can manage tables, create reservations, and assign seats',

    # Customer management permissions
    'customers:view': 'Can view customer profiles, VIP status, and order history',

    # System settings permissions
    'settings:manage': 'Full administrative control to configure roles and permissions',
}

# Group permissions by category for UI configuration
PERMISSION_CATEGORIES = {
    'Orders & POS': [
        'orders:view',
        'orders:create',
        'orders:update_status',
        'orders:cancel',
    ],
    'Kitchen Display (KDS)': [
        'kitchen:view_orders',
        'kitchen:update_status',
    ],
    'Delivery & Logistics': [
        'deliveries:view_assigned',
        'deliveries:update_status',
    ],
    'Menu & Pricing': [
        'menu:view',
        'menu:manage',
        'menu:toggle_availability',
    ],
    'Inventory & Stock': [
        'inventory:view',
        'inventory:manage',
    ],
    'Reports & Analytics': [
        'reports:view',
    ],
    'Staff & Scheduling': [
        'staff:view',
        'staff:manage',
    ],
    'Tables & Reservations': [
        'reservations:view',
        'reservations:manage',
    ],
    'Customer Management': [
        'customers:view',
    ],
    'System Administration': [
        'settings:manage',
    ],
}

# Default role mappings exactly matching Section 18
DEFAULT_ROLE_PERMISSIONS = {
    'super_admin': list(PERMISSIONS.keys()),  # Whole Admin Manager - Master Unrestricted Access
    'admin': list(PERMISSIONS.keys()),  # Full access
    'manager': [
        'orders:view',
        'orders:create',
        'orders:update_status',
        'orders:cancel',
        'kitchen:view_orders',
        'kitchen:update_status',
        'deliveries:view_assigned',
        'deliveries:update_status',
        'menu:view',
        'menu:manage',
        'menu:toggle_availability',
        'inventory:view',
        'inventory:manage',
        'reports:view',
        'staff:view',
        'staff:manage',
        'reservations:view',
        'reservations:manage',
        'customers:view',
    ],
    'kitchen_staff': [
        'kitchen:view_orders',
        'kitchen:update_status',
        'menu:toggle_availability',
    ],
    'delivery_staff': [
        'deliveries:view_assigned',
        'deliveries:update_status',
    ],
    'cashier_front': [
        'orders:view',
        'orders:create',
        'orders:update_status',
        'menu:view',
        'menu:toggle_availability',
        'reservations:view',
        'reservations:manage',
        'customers:view',
    ],
    'customer': [
        'menu:view',
    ],
}

