from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from apps.accounts.constants import DEFAULT_ROLE_PERMISSIONS
from apps.accounts.models import RolePermissionConfig
from apps.inventory.models import InventoryItem, Recipe, RecipeIngredient, Supplier
from apps.menu.models import Category, Dish, DishExtraOption, DishPortionOption
from apps.orders.models import Order, OrderItem
from apps.reservations.models import Reservation, Table
from apps.staff.models import StaffMember

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds initial sample data for Restaurant Management (complies with Section 18: Roles & Permissions)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Seeding Restaurant Management data...'))

        # 1. Seed Configurable Role Permissions
        role_metadata = {
            'admin': ('Owner/Admin', 'Full unrestricted access to all restaurant modules, settings, and staff operations.'),
            'manager': ('Manager', 'Access to orders, menu, inventory, analytics/reports, and staff-related functions.'),
            'kitchen_staff': ('Kitchen Staff', 'Restricted access to kitchen display system (KDS) and item availability toggling.'),
            'delivery_staff': ('Delivery Staff', 'Access to view assigned delivery orders and update delivery status.'),
            'cashier_front': ('Cashier/Front Staff', 'Access to orders, POS billing, tables/reservations, and customer operations.'),
            'customer': ('Customer', 'Customer ordering, table booking, and personal profile management.'),
        }

        for role_key, perms in DEFAULT_ROLE_PERMISSIONS.items():
            name, desc = role_metadata.get(role_key, (role_key.capitalize(), ''))
            config, created = RolePermissionConfig.objects.get_or_create(
                role=role_key,
                defaults={
                    'name': name,
                    'description': desc,
                    'permissions': perms,
                    'is_customizable': role_key != 'admin',
                }
            )
            if not created and not config.permissions:
                config.permissions = perms
                config.save()
        self.stdout.write(self.style.SUCCESS('Configurable role permissions initialized.'))

        # 2. Seed Users for Each Role (Complies with Section 18)
        users_to_seed = [
            {
                'username': 'admin',
                'email': 'admin@restaurant.com',
                'first_name': 'Owner',
                'last_name': 'Admin',
                'role': User.Role.ADMIN,
                'password': 'admin123',
                'is_staff': True,
                'is_superuser': True,
            },
            {
                'username': 'manager_sarah',
                'email': 'manager@restaurant.com',
                'first_name': 'Sarah',
                'last_name': 'Jenkins',
                'role': User.Role.MANAGER,
                'password': 'manager123',
                'is_staff': True,
            },
            {
                'username': 'chef_rajesh',
                'email': 'chef@restaurant.com',
                'first_name': 'Rajesh',
                'last_name': 'Kumar',
                'role': User.Role.KITCHEN_STAFF,
                'password': 'kitchen123',
            },
            {
                'username': 'delivery_dave',
                'email': 'delivery@restaurant.com',
                'first_name': 'Dave',
                'last_name': 'Miller',
                'role': User.Role.DELIVERY_STAFF,
                'password': 'delivery123',
            },
            {
                'username': 'cashier_linda',
                'email': 'cashier@restaurant.com',
                'first_name': 'Linda',
                'last_name': 'Taylor',
                'role': User.Role.CASHIER_FRONT,
                'password': 'cashier123',
            },
            {
                'username': 'customer_mark',
                'email': 'mark@example.com',
                'first_name': 'Mark',
                'last_name': 'Jecno',
                'role': User.Role.CUSTOMER,
                'password': 'customer123',
                'phone': '+353 87 123 4567',
                'is_vip': True,
            },
        ]

        seeded_users = {}
        for udata in users_to_seed:
            pwd = udata.pop('password')
            user, created = User.objects.get_or_create(username=udata['username'], defaults=udata)
            if created or not user.has_usable_password():
                user.set_password(pwd)
                user.save()
            seeded_users[user.role] = user

        self.stdout.write(self.style.SUCCESS('All Section 18 role accounts created with standard passwords.'))

        # 3. Categories
        categories_data = [
            {'name': 'Biryani & Rice', 'slug': 'biryani-rice', 'order': 1},
            {'name': 'Curries & Gravies', 'slug': 'curries-gravies', 'order': 2},
            {'name': 'Tandoori & Grill', 'slug': 'tandoori-grill', 'order': 3},
            {'name': 'Breads & Sides', 'slug': 'breads-sides', 'order': 4},
            {'name': 'Desserts & Sweets', 'slug': 'desserts-sweets', 'order': 5},
            {'name': 'Beverages', 'slug': 'beverages', 'order': 6},
        ]
        created_categories = {}
        for cat in categories_data:
            c, _ = Category.objects.get_or_create(
                slug=cat['slug'],
                defaults={'name': cat['name'], 'order': cat['order']}
            )
            created_categories[cat['slug']] = c

        # 4. Dishes
        dishes_data = [
            {
                'category': created_categories['biryani-rice'],
                'name': 'Royal Chicken Dum Biryani',
                'price': Decimal('14.99'),
                'station': Dish.Station.BIRYANI,
                'spicy_level': 2,
                'is_bestseller': True,
                'is_popular': True,
                'description': 'Slow-cooked aromatic basmati rice layered with spiced tender chicken and saffron.',
                'image_url': 'https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=800',
                'available_ingredients': ['Fried Onions', 'Coriander / Mint', 'Cashew Nuts', 'Boiled Egg'],
                'available_modifiers': {'spice_level': ['Mild', 'Medium', 'Hot', 'Extra Hot']},
            },
            {
                'category': created_categories['curries-gravies'],
                'name': 'Kashmiri Lamb Rogan Josh',
                'price': Decimal('16.99'),
                'station': Dish.Station.CURRY,
                'spicy_level': 2,
                'is_bestseller': True,
                'is_popular': True,
                'description': 'Tender slow-braised lamb shanks simmered in aromatic Kashmiri spices and yogurt gravy.',
                'image_url': 'https://images.unsplash.com/photo-1585937421612-70a008356fbe?w=800',
                'available_ingredients': ['Ginger Slivers', 'Fresh Coriander', 'Garlic'],
                'available_modifiers': {'spice_level': ['Medium', 'Hot', 'Very Hot']},
            },
            {
                'category': created_categories['curries-gravies'],
                'name': 'Old Delhi Butter Chicken',
                'price': Decimal('13.99'),
                'station': Dish.Station.CURRY,
                'spicy_level': 1,
                'is_popular': True,
                'description': 'Tandoor-charred chicken tikka simmered in a silky tomato, fenugreek, and cream sauce.',
                'image_url': 'https://images.unsplash.com/photo-1603894584373-5ac82b2ae398?w=800',
                'available_ingredients': ['Fenugreek / Kasoori Methi', 'Butter Cream Swirl', 'Cashew Paste'],
                'available_modifiers': {'spice_level': ['Mild', 'Medium']},
            },
            {
                'category': created_categories['tandoori-grill'],
                'name': 'Tandoori Seekh Kebab',
                'price': Decimal('12.50'),
                'station': Dish.Station.GRILL,
                'spicy_level': 3,
                'is_special': True,
                'description': 'Minced spiced mutton skewered and roasted to perfection in clay tandoor oven.',
                'image_url': 'https://images.unsplash.com/photo-1599488615731-7e5c2823ff28?w=800',
                'available_ingredients': ['Chaat Masala', 'Sliced Onions', 'Mint Chutney'],
                'available_modifiers': {'preparation': ['Well Done / Charred', 'Standard Juicy']},
            },
            {
                'category': created_categories['breads-sides'],
                'name': 'Garlic Butter Naan',
                'price': Decimal('3.99'),
                'station': Dish.Station.BREADS,
                'spicy_level': 0,
                'description': 'Clay-oven baked leavened flatbread glazed with crushed garlic and melted herb butter.',
                'image_url': 'https://images.unsplash.com/photo-1601050690597-df0568f70950?w=800',
            },
            {
                'category': created_categories['desserts-sweets'],
                'name': 'Pistachio Shahi Gulab Jamun',
                'price': Decimal('5.99'),
                'station': Dish.Station.DESSERT,
                'spicy_level': 0,
                'description': 'Golden milk-solid dumplings soaked in rose cardamom sugar syrup, topped with roasted pistachios.',
                'image_url': 'https://images.unsplash.com/photo-1605197148560-639a0684f88e?w=800',
            },
        ]

        created_dishes = []
        for dish_data in dishes_data:
            dish, _ = Dish.objects.get_or_create(
                name=dish_data['name'],
                defaults=dish_data
            )
            created_dishes.append(dish)

            if not dish.portion_options.exists():
                DishPortionOption.objects.create(dish=dish, name='Regular / Single', price_delta=Decimal('0.00'))
                DishPortionOption.objects.create(dish=dish, name='Full / Family Sharing', price_delta=Decimal('6.50'))

            if not dish.extra_options.exists():
                DishExtraOption.objects.create(dish=dish, name='Extra Raita & Mint Dip', price=Decimal('1.50'))
                DishExtraOption.objects.create(dish=dish, name='Extra Curry Gravy', price=Decimal('2.50'))

        # 5. Tables
        tables = [
            {'number': 'T-01', 'capacity': 2, 'status': Table.Status.AVAILABLE},
            {'number': 'T-02', 'capacity': 4, 'status': Table.Status.OCCUPIED, 'guest_name': 'Mr. David Smith', 'current_order': '#ORD-101'},
            {'number': 'T-03', 'capacity': 4, 'status': Table.Status.RESERVED, 'guest_name': 'Emma Watson', 'time_slot': '19:30'},
            {'number': 'T-04', 'capacity': 6, 'status': Table.Status.AVAILABLE},
            {'number': 'T-05', 'capacity': 8, 'status': Table.Status.AVAILABLE},
            {'number': 'T-06', 'capacity': 2, 'status': Table.Status.AVAILABLE},
        ]
        for tbl in tables:
            Table.objects.get_or_create(number=tbl['number'], defaults=tbl)

        # 6. Suppliers & Inventory Items
        supplier_valley, _ = Supplier.objects.get_or_create(name='Valley Farms & Meats', defaults={'contact_name': 'Eamonn Walsh', 'phone': '+3531234567', 'email': 'orders@valleyfarms.ie'})
        supplier_silk, _ = Supplier.objects.get_or_create(name='Silk Road Spices Ltd', defaults={'contact_name': 'Amir Khan', 'phone': '+3531234568', 'email': 'info@silkroadspices.ie'})
        supplier_green, _ = Supplier.objects.get_or_create(name='Fresh Green Produce Dublin', defaults={'contact_name': 'Mary Kelly', 'phone': '+3531234569', 'email': 'orders@freshgreen.ie'})
        supplier_pack, _ = Supplier.objects.get_or_create(name='EcoPack Packaging Ireland', defaults={'contact_name': 'Brian Byrne', 'phone': '+3531234570', 'email': 'sales@ecopack.ie'})

        inventory = [
            {'name': 'Basmati Rice Premium (50kg)', 'category': InventoryItem.Category.RICE_GRAINS, 'current_stock': Decimal('120.00'), 'minimum_stock': Decimal('40.00'), 'reorder_level': Decimal('50.00'), 'unit': 'kg', 'purchase_price': Decimal('2.20'), 'supplier': 'Himalayan Mills Ltd'},
            {'name': 'Free-Range Fresh Chicken', 'category': InventoryItem.Category.MEAT_POULTRY, 'current_stock': Decimal('45.00'), 'minimum_stock': Decimal('15.00'), 'reorder_level': Decimal('20.00'), 'unit': 'kg', 'purchase_price': Decimal('6.50'), 'supplier_ref': supplier_valley},
            {'name': 'Irish Prime Angus Beef Mince', 'category': InventoryItem.Category.BEEF_LAMB, 'current_stock': Decimal('30.00'), 'minimum_stock': Decimal('10.00'), 'reorder_level': Decimal('15.00'), 'unit': 'kg', 'purchase_price': Decimal('11.50'), 'supplier_ref': supplier_valley},
            {'name': 'Chakki Atta Whole Wheat Flour', 'category': InventoryItem.Category.FLOUR_BAKERY, 'current_stock': Decimal('80.00'), 'minimum_stock': Decimal('25.00'), 'reorder_level': Decimal('35.00'), 'unit': 'kg', 'purchase_price': Decimal('1.75')},
            {'name': 'Pure Mustard & Sunflower Oil', 'category': InventoryItem.Category.OILS_FATS, 'current_stock': Decimal('50.00'), 'minimum_stock': Decimal('15.00'), 'reorder_level': Decimal('20.00'), 'unit': 'litre', 'purchase_price': Decimal('3.20')},
            {'name': 'Brown Onions & Red Tomatoes', 'category': InventoryItem.Category.VEGETABLES, 'current_stock': Decimal('65.00'), 'minimum_stock': Decimal('30.00'), 'reorder_level': Decimal('40.00'), 'unit': 'kg', 'purchase_price': Decimal('1.40'), 'supplier_ref': supplier_green},
            {'name': 'Signature Biryani Curry Sauce', 'category': InventoryItem.Category.SAUCES, 'current_stock': Decimal('25.00'), 'minimum_stock': Decimal('8.00'), 'reorder_level': Decimal('10.00'), 'unit': 'kg', 'purchase_price': Decimal('4.80')},
            {'name': 'Kashmiri Saffron & Garam Masala', 'category': InventoryItem.Category.SPICES_SEASONING, 'current_stock': Decimal('10.00'), 'minimum_stock': Decimal('3.00'), 'reorder_level': Decimal('4.00'), 'unit': 'kg', 'purchase_price': Decimal('18.00'), 'supplier_ref': supplier_silk},
            {'name': 'Buffalo Paneer & Fresh Curd', 'category': InventoryItem.Category.DAIRY, 'current_stock': Decimal('20.00'), 'minimum_stock': Decimal('8.00'), 'reorder_level': Decimal('10.00'), 'unit': 'kg', 'purchase_price': Decimal('7.50')},
            {'name': 'Mango Lassi & Refreshing Drinks', 'category': InventoryItem.Category.DRINKS, 'current_stock': Decimal('120.00'), 'minimum_stock': Decimal('30.00'), 'reorder_level': Decimal('40.00'), 'unit': 'pieces', 'purchase_price': Decimal('1.20')},
            {'name': 'Eco Kraft Food Containers & Bags', 'category': InventoryItem.Category.PACKAGING, 'current_stock': Decimal('500.00'), 'minimum_stock': Decimal('100.00'), 'reorder_level': Decimal('150.00'), 'unit': 'pieces', 'purchase_price': Decimal('0.22'), 'supplier_ref': supplier_pack},
        ]
        created_items = {}
        for inv in inventory:
            inv_copy = dict(inv)
            name = inv_copy.pop('name')
            obj, _ = InventoryItem.objects.get_or_create(name=name, defaults=inv_copy)
            created_items[name] = obj

        # Seed Recipe / BOM for first Biryani dish
        biryani_dish = Dish.objects.filter(category__name='Biryani').first()
        if biryani_dish:
            recipe, _ = Recipe.objects.get_or_create(
                dish=biryani_dish,
                defaults={
                    'name': f"Authentic Recipe for {biryani_dish.name}",
                    'yield_portions': 1,
                    'instructions': "Marinate chicken in curd and spices, parboil basmati rice, layer with sauce and saffron, seal and dum cook.",
                    'prep_time_minutes': 25
                }
            )
            chk_item = created_items.get('Free-Range Fresh Chicken')
            rice_item = created_items.get('Basmati Rice Premium (50kg)')
            sauce_item = created_items.get('Signature Biryani Curry Sauce')

            if chk_item:
                RecipeIngredient.objects.get_or_create(recipe=recipe, inventory_item=chk_item, defaults={'quantity': Decimal('200.000'), 'unit': 'g', 'notes': 'Fresh diced'})
            if rice_item:
                RecipeIngredient.objects.get_or_create(recipe=recipe, inventory_item=rice_item, defaults={'quantity': Decimal('100.000'), 'unit': 'g', 'notes': 'Aged Basmati'})
            if sauce_item:
                RecipeIngredient.objects.get_or_create(recipe=recipe, inventory_item=sauce_item, defaults={'quantity': Decimal('20.000'), 'unit': 'g', 'notes': 'Spiced Biryani gravy'})

        # 7. Staff Profile Records
        staff = [
            {
                'name': 'Rajesh Kumar',
                'role': StaffMember.Role.HEAD_CHEF,
                'shift': StaffMember.Shift.MORNING,
                'status': StaffMember.Status.ACTIVE,
                'assigned_section': 'Kitchen - Main Station',
                'phone': '+353 87 555 1001',
                'user': seeded_users.get(User.Role.KITCHEN_STAFF),
            },
            {
                'name': 'Dave Miller',
                'role': StaffMember.Role.SERVER,
                'shift': StaffMember.Shift.EVENING,
                'status': StaffMember.Status.ACTIVE,
                'assigned_section': 'Deliveries & Logistics',
                'phone': '+353 87 555 1002',
                'user': seeded_users.get(User.Role.DELIVERY_STAFF),
            },
            {
                'name': 'Sarah Jenkins',
                'role': StaffMember.Role.FLOOR_MANAGER,
                'shift': StaffMember.Shift.FULL_DAY,
                'status': StaffMember.Status.ACTIVE,
                'assigned_section': 'Front of House / Floor',
                'phone': '+353 87 555 1003',
                'user': seeded_users.get(User.Role.MANAGER),
            },
            {
                'name': 'Linda Taylor',
                'role': StaffMember.Role.HOST,
                'shift': StaffMember.Shift.EVENING,
                'status': StaffMember.Status.ACTIVE,
                'assigned_section': 'Cashier Counter & POS',
                'phone': '+353 87 555 1004',
                'user': seeded_users.get(User.Role.CASHIER_FRONT),
            },
        ]
        for s in staff:
            StaffMember.objects.get_or_create(name=s['name'], defaults=s)

        # 8. Sample Orders with Delivery Assignment
        delivery_staff_user = seeded_users.get(User.Role.DELIVERY_STAFF)
        if created_dishes and not Order.objects.exists():
            order1 = Order.objects.create(
                customer_name='Mark Jecno',
                customer_phone='+353 87 123 4567',
                dining_type=Order.DiningType.DELIVERY,
                status=Order.Status.OUT_FOR_DELIVERY,
                payment_status=Order.PaymentStatus.PAID,
                payment_method=Order.PaymentMethod.APPLE_PAY,
                subtotal=Decimal('16.99'),
                tax=Decimal('2.00'),
                delivery_fee=Decimal('3.50'),
                total_amount=Decimal('22.49'),
                delivery_address='12 Fitzwilliam Square, Dublin 2',
                notes='Ring Apt 3 buzzer, leave at reception door.',
                estimated_time_minutes=25,
                assigned_delivery_staff=delivery_staff_user,
            )
            OrderItem.objects.create(
                order=order1,
                dish=created_dishes[1],
                name=created_dishes[1].name,
                quantity=1,
                price=created_dishes[1].price,
                station='curry',
                customizations={'spice': 'Medium', 'gravy': 'Extra on side'}
            )

            order2 = Order.objects.create(
                customer_name='Sarah Ahmed',
                customer_phone='+353 89 222 2041',
                dining_type=Order.DiningType.DINE_IN,
                table_number='T-02',
                status=Order.Status.PREPARING,
                payment_status=Order.PaymentStatus.PAID,
                payment_method=Order.PaymentMethod.CARD,
                subtotal=Decimal('30.98'),
                tax=Decimal('3.10'),
                delivery_fee=Decimal('0.00'),
                total_amount=Decimal('34.08'),
                estimated_time_minutes=20
            )
            OrderItem.objects.create(
                order=order2,
                dish=created_dishes[0],
                name=created_dishes[0].name,
                quantity=2,
                price=created_dishes[0].price,
                station='biryani'
            )

        self.stdout.write(self.style.SUCCESS('Successfully seeded restaurant database!'))
