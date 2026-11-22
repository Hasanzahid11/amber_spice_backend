from datetime import date
from decimal import Decimal
from django.db import migrations


def seed_promotions(apps, schema_editor):
    Promotion = apps.get_model('engagement', 'Promotion')
    promos = [
        {
            'code': 'SPICE20',
            'title': 'Welcome First Order Feast',
            'description': 'Enjoy 20% off your entire online dining delivery or takeaway order from Amber Spice.',
            'discount_type': 'percentage',
            'discount_value': Decimal('20.00'),
            'min_spend': Decimal('25.00'),
            'valid_until': date(2027, 12, 31),
            'usage_limit': 1000,
            'is_active': True,
            'first_order_only': False,
            'badge': '20% OFF FIRST ORDER',
            'image_url': 'https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80',
        },
        {
            'code': 'DUBLIN10',
            'title': 'Dublin Diners 10% Welcome Discount',
            'description': '10% off your online delivery or takeaway order across Dublin.',
            'discount_type': 'percentage',
            'discount_value': Decimal('10.00'),
            'min_spend': Decimal('20.00'),
            'valid_until': date(2027, 12, 31),
            'usage_limit': 1000,
            'is_active': True,
            'first_order_only': False,
            'badge': '10% WELCOME',
            'image_url': 'https://images.unsplash.com/photo-1565557623262-b51c2513a641?auto=format&fit=crop&w=800&q=80',
        },
        {
            'code': 'FEAST20',
            'title': 'Midweek Biryani Feast',
            'description': '20% off all Biryani platters & curries on mid-week dining.',
            'discount_type': 'percentage',
            'discount_value': Decimal('20.00'),
            'min_spend': Decimal('35.00'),
            'valid_until': date(2027, 12, 31),
            'usage_limit': 500,
            'is_active': True,
            'first_order_only': False,
            'badge': '20% MIDWEEK SPECIAL',
            'image_url': 'https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?auto=format&fit=crop&w=800&q=80',
        },
        {
            'code': 'FAMILY15',
            'title': 'Grand Royal Family Banquet Deal',
            'description': '€15 instant reduction on Grand Family Combos serving 4 or more diners.',
            'discount_type': 'fixed',
            'discount_value': Decimal('15.00'),
            'min_spend': Decimal('50.00'),
            'valid_until': date(2027, 12, 31),
            'usage_limit': 500,
            'is_active': True,
            'first_order_only': False,
            'badge': '€15 OFF FAMILY DEAL',
            'image_url': 'https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=800&q=80',
        },
        {
            'code': 'CURRY15',
            'title': 'Mid-Week Heritage Curry Night',
            'description': '15% off all authentic curries on orders over €30.',
            'discount_type': 'percentage',
            'discount_value': Decimal('15.00'),
            'min_spend': Decimal('30.00'),
            'valid_until': date(2027, 12, 31),
            'usage_limit': 500,
            'is_active': True,
            'first_order_only': False,
            'badge': '15% CURRY NIGHT',
            'image_url': 'https://images.unsplash.com/photo-1603894584373-5ac82b2ae398?auto=format&fit=crop&w=800&q=80',
        },
    ]
    for p in promos:
        Promotion.objects.update_or_create(
            code=p['code'],
            defaults=p,
        )


def unseed_promotions(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('engagement', '0004_review_admin_reply_review_replied_at'),
    ]

    operations = [
        migrations.RunPython(seed_promotions, unseed_promotions),
    ]
