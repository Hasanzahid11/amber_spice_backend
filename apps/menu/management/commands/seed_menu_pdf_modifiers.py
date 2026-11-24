from decimal import Decimal
from django.core.management.base import BaseCommand
from apps.menu.models import Dish, DishExtraOption, DishPortionOption


COMMON_ALLERGENS = ['Nut Allergy', 'Dairy / Lactose', 'Gluten', 'Shellfish']

CURRY_PREP = [
    'Less Ghee & Oil',
    'Sauce on the Side',
    'No Fresh Coriander',
    'No Raw Onions',
    'No Dairy / Cream Garnish',
]

BIRYANI_PREP = [
    'Less Ghee & Oil',
    'No Nuts / Raisins',
    'No Fresh Coriander',
    'No Boiled Egg',
    'Raita on the Side',
]

GRILL_SEAFOOD_PREP = [
    'Sauce / Chutney on the Side',
    'Less Oil / Butter',
    'Well Done / Extra Char',
    'No Fresh Coriander',
]

MEZZE_SALAD_PREP = [
    'Dressing / Olive Oil on the Side',
    'No Walnuts / Nuts',
    'No Garlic',
    'No Pomegranate',
]

NOODLES_RICE_PREP = [
    'No Egg',
    'No Spring Onion',
    'Less Soy / Salt',
    'Extra Fresh Chilli',
]

BURGER_KIDS_PREP = [
    'No Pickles',
    'No Cheese',
    'No Salad / Lettuce',
    'Sauce on the Side',
]

DESSERT_PREP = [
    'Serve Warm',
    'No Nuts / Pistachio',
    'Sauce / Syrup on the Side',
]


def _classify_dish(dish: Dish):
    cat = (dish.category.name if dish.category else '').lower()
    name = (dish.name or '').lower()

    if 'ice cream' in name:
        return {
            'allows_spice_level': False,
            'prep_preferences': ['In Bowl', 'No Wafer'],
            'allergen_options': ['Dairy / Lactose', 'Nut Allergy'],
            'portions': [
                ('Vanilla Scoop', '1 Scoop', '0.00', '1.00'),
                ('Chocolate Scoop', '1 Scoop', '0.00', '1.00'),
                ('Saffron Scoop', '1 Scoop', '0.00', '1.00'),
            ],
            'extras': [
                ('Extra Scoop', '3.00'),
                ('Chocolate Sauce', '1.00'),
            ],
        }

    if 'sorbet' in name:
        return {
            'allows_spice_level': False,
            'prep_preferences': ['In Bowl', 'Vegan Friendly'],
            'allergen_options': ['Nut Allergy'],
            'portions': [
                ('Mango Sorbet', '1 Scoop', '0.00', '1.00'),
                ('Strawberry Sorbet', '1 Scoop', '0.00', '1.00'),
                ('Lemon Sorbet', '1 Scoop', '0.00', '1.00'),
            ],
            'extras': [('Extra Scoop', '3.00')],
        }

    if 'dessert' in cat or 'sweet' in cat or any(k in name for k in ['gulab jamun', 'baklava', 'oum ali', 'malabia', 'panna cotta', 'cheesecake']):
        return {
            'allows_spice_level': False,
            'prep_preferences': DESSERT_PREP,
            'allergen_options': ['Nut Allergy', 'Dairy / Lactose', 'Gluten'],
            'portions': [],
            'extras': [
                ('Add Vanilla Ice Cream Scoop', '3.00'),
                ('Add Saffron Ice Cream Scoop', '3.50'),
            ],
        }

    if 'beverage' in cat or 'drink' in cat or 'lassi' in name:
        return {
            'allows_spice_level': False,
            'prep_preferences': ['Less Ice', 'No Ice', 'Less Sugar'],
            'allergen_options': ['Dairy / Lactose', 'Nut Allergy'],
            'portions': [
                ('Regular (330ml)', 'Single', '0.00', '1.00'),
                ('Large Glass (500ml)', 'Large', '1.50', '1.50'),
            ],
            'extras': [],
        }

    if 'kid' in cat or 'nuggets' in name or 'mini burger' in name:
        return {
            'allows_spice_level': False,
            'prep_preferences': BURGER_KIDS_PREP,
            'allergen_options': ['Gluten', 'Dairy / Lactose'],
            'portions': [],
            'extras': [
                ('Extra Ketchup Dip', '0.50'),
                ('Kids Juice Box', '2.00'),
            ],
        }

    if 'chip' in cat or 'fries' in name:
        return {
            'allows_spice_level': 'masala' in name or 'cajun' in name,
            'prep_preferences': ['Extra Crispy', 'No Salt'],
            'allergen_options': ['Gluten'],
            'portions': [
                ('Regular Portion', 'Serves 1', '0.00', '1.00'),
                ('Large Sharing', 'Serves 2', '2.50', '1.75'),
            ],
            'extras': [
                ('Garlic Mayo Dip', '1.50'),
                ('House Curry Sauce', '2.50'),
                ('Melted Cheddar', '1.50'),
            ],
        }

    if 'burger' in cat or 'burger' in name:
        return {
            'allows_spice_level': True,
            'prep_preferences': BURGER_KIDS_PREP,
            'allergen_options': ['Gluten', 'Dairy / Lactose', 'Sesame'],
            'portions': [
                ('Burger Only', 'Single', '0.00', '1.00'),
                ('Meal (Classic Fries & Drink)', 'Combo', '5.50', '1.00'),
                ('Masala Meal (Masala Fries & Drink)', 'Combo', '6.50', '1.00'),
            ],
            'extras': [
                ('Extra Cheddar Cheese', '1.50'),
                ('Garlic Mayo Dip', '1.50'),
                ('Crispy Onion Bhaji Topping', '2.00'),
            ],
        }

    if 'bread' in cat or 'naan' in name or 'roti' in name or 'paratha' in name:
        return {
            'allows_spice_level': False,
            'prep_preferences': ['With Butter / Ghee', 'Dry (No Butter)', 'Extra Crisp'],
            'allergen_options': ['Gluten', 'Dairy / Lactose', 'Nut Allergy'],
            'portions': [],
            'extras': [
                ('Mint Chutney Dip', '1.50'),
                ('Garlic Butter Brush', '1.00'),
            ],
        }

    if 'rice' in name and 'fried rice' not in name and 'biryani' not in name:
        return {
            'allows_spice_level': False,
            'prep_preferences': ['Less Ghee', 'No Fresh Coriander'],
            'allergen_options': ['Dairy / Lactose'],
            'portions': [],
            'extras': [('Mint Raita', '2.00')],
        }

    if 'boil' in cat or 'seafood boil' in name:
        return {
            'allows_spice_level': True,
            'prep_preferences': ['Extra Garlic Butter', 'Butter Sauce on the Side', 'No Corn'],
            'allergen_options': ['Shellfish', 'Dairy / Lactose'],
            'portions': [
                ('Golden Garlic Butter Boil', 'Classic House', '0.00', '1.00'),
                ('Cajun Spiced Butter Boil', 'Aromatic Heat', '0.00', '1.00'),
                ('Fiery Amber Boil', 'Extra Chilli', '0.00', '1.00'),
            ],
            'extras': [
                ('Extra King Prawns', '9.50'),
                ('Extra Baby Potatoes & Sweetcorn', '4.50'),
                ('Garlic Naan (2pcs)', '7.50'),
                ('Extra Garlic Butter Dip', '2.50'),
            ],
        }

    if 'biriyani' in cat or 'biryani' in cat or 'biryani' in name:
        return {
            'allows_spice_level': True,
            'prep_preferences': BIRYANI_PREP,
            'allergen_options': COMMON_ALLERGENS,
            'portions': [
                ('Single Portion', 'Serves 1', '0.00', '1.00'),
                ('Couple Pot', 'Serves 2', '15.50', '1.85'),
                ('Family Handi', 'Serves 4', '34.00', '3.50'),
            ],
            'extras': [
                ('Mint Raita', '2.00'),
                ('Mirchi Ka Salan', '3.00'),
                ('Garlic Naan', '4.50'),
                ('Poppadoms & Chutneys', '2.50'),
            ],
        }

    if 'noodle' in cat or 'chow mein' in name or 'fried rice' in name:
        return {
            'allows_spice_level': True,
            'prep_preferences': NOODLES_RICE_PREP,
            'allergen_options': ['Gluten', 'Shellfish', 'Soy', 'Egg'],
            'portions': [
                ('Regular', 'Serves 1', '0.00', '1.00'),
                ('Large Sharing', 'Serves 2', '8.50', '1.75'),
            ],
            'extras': [
                ('Chilli Garlic Oil', '1.50'),
                ('Classic Fries', '5.00'),
            ],
        }

    if 'cold mezze' in cat or 'salad' in cat or any(k in name for k in ['hummus', 'moutabal', 'labneh', 'muhammara', 'tabbouleh', 'fattoush']):
        is_platter = 'platter' in name
        return {
            'allows_spice_level': False,
            'prep_preferences': MEZZE_SALAD_PREP,
            'allergen_options': ['Nut Allergy', 'Dairy / Lactose', 'Gluten', 'Sesame'],
            'portions': [
                ('Standard Platter', 'Serves 2–3', '0.00', '1.00'),
                ('Large Party Platter', 'Serves 4–5', '18.00', '1.80'),
            ] if is_platter else [],
            'extras': [
                ('Extra Tandoori Naan', '3.50'),
                ('Marinated Olives', '3.00'),
            ],
        }

    if 'starter' in cat or 'chaat' in cat or 'soup' in cat or 'shorba' in name or 'bhaji' in name or 'samosa' in name:
        return {
            'allows_spice_level': True,
            'prep_preferences': ['Chutney on the Side', 'No Yoghurt', 'No Fresh Coriander', 'No Raw Onions'],
            'allergen_options': ['Gluten', 'Dairy / Lactose', 'Nut Allergy'],
            'portions': [],
            'extras': [
                ('Extra Mint Chutney', '1.50'),
                ('Extra Tamarind Chutney', '1.50'),
            ],
        }

    if 'grill' in cat or 'tandoori' in cat or 'fish' in cat or 'seafood' in cat:
        is_platter = 'platter' in name
        return {
            'allows_spice_level': True,
            'prep_preferences': GRILL_SEAFOOD_PREP,
            'allergen_options': ['Shellfish', 'Dairy / Lactose', 'Nut Allergy'],
            'portions': [
                ('Standard Sharing Platter', 'Serves 2–3', '0.00', '1.00'),
                ('Grand Family Platter', 'Serves 4–5', '35.00', '1.80'),
            ] if is_platter else [],
            'extras': [
                ('Saffron Rice', '5.50'),
                ('Garlic Naan', '4.50'),
                ('Classic Fries', '5.00'),
                ('Mint Chutney & Garlic Toum', '2.00'),
            ],
        }

    # Default: Indian Classics - Chicken & Meat / Curries & Gravies / Vegetarian Signatures
    return {
        'allows_spice_level': True,
        'prep_preferences': CURRY_PREP,
        'allergen_options': COMMON_ALLERGENS,
        'portions': [
            ('Single Portion', 'Serves 1', '0.00', '1.00'),
            ('Couple Sharing', 'Serves 2', '14.50', '1.80'),
            ('Family Feast', 'Serves 4', '32.00', '3.50'),
        ],
        'extras': [
            ('Steamed Basmati Rice', '4.00'),
            ('Jeera / Pilau Rice', '4.50'),
            ('Plain Naan', '3.50'),
            ('Garlic Naan', '4.50'),
            ('Mint Raita', '2.00'),
            ('Poppadoms & Chutneys', '2.50'),
        ],
    }


class Command(BaseCommand):
    help = 'Seed professional serving sizes, side pairings, prep preferences & allergen options matching Amber Spice Menu PDF.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Overwrite existing portion_options and extra_options on all dishes.',
        )

    def handle(self, *args, **options):
        force = options['force']
        updated_count = 0

        for dish in Dish.objects.select_related('category').all():
            spec = _classify_dish(dish)
            dish.allows_spice_level = spec['allows_spice_level']
            dish.prep_preferences = spec['prep_preferences']
            dish.allergen_options = spec['allergen_options']
            dish.save(update_fields=['allows_spice_level', 'prep_preferences', 'allergen_options'])

            if force or not dish.portion_options.exists():
                dish.portion_options.all().delete()
                for name, serving_info, delta, mult in spec['portions']:
                    DishPortionOption.objects.create(
                        dish=dish,
                        name=name,
                        serving_info=serving_info,
                        price_delta=Decimal(delta),
                        inventory_multiplier=Decimal(mult),
                    )

            if force or not dish.extra_options.exists():
                dish.extra_options.all().delete()
                for name, price in spec['extras']:
                    DishExtraOption.objects.create(
                        dish=dish,
                        name=name,
                        price=Decimal(price),
                    )

            updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(f'Successfully configured menu PDF customization rules for {updated_count} dishes.')
        )
