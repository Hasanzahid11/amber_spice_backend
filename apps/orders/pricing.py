from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.menu.models import Dish


def money(value):
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def checkout_policy():
    from apps.engagement.models import RestaurantProfile
    profile = RestaurantProfile.objects.first()
    if profile and not profile.ordering_enabled:
        raise ValidationError({'detail': 'The restaurant is not accepting orders right now.'})
    return profile


def price_items(items, dining_type):
    """Only catalog values determine prices, names and kitchen stations."""
    result = []
    subtotal = Decimal('0')
    dishes = {dish.id: dish for dish in Dish.objects.select_related('category').prefetch_related(
        'portion_options', 'extra_options').filter(id__in=[item['dish_id'] for item in items])}
    for item in items:
        dish = dishes.get(item['dish_id'])
        if not dish or not dish.is_available or not dish.category.is_active:
            raise ValidationError({'items': 'A selected dish is unavailable. Refresh the menu.'})
        customs = item.get('customizations', {})
        price = dish.price
        normalized = {}
        if customs.get('portionName'):
            portion = next((p for p in dish.portion_options.all() if p.name == customs['portionName']), None)
            if not portion:
                raise ValidationError({'items': f'Invalid portion for {dish.name}.'})
            price += portion.price_delta
            normalized['portionName'] = portion.name
        extras = customs.get('extras', [])
        if not isinstance(extras, list) or any(not isinstance(extra, dict) for extra in extras):
            raise ValidationError({'items': 'Extras must be a list of selected options.'})
        names = [extra.get('name') for extra in extras]
        if len(names) != len(set(str(name) for name in names)):
            raise ValidationError({'items': 'Duplicate extras are not allowed.'})
        catalog_extras = {extra.name: extra for extra in dish.extra_options.all()}
        normalized['extras'] = []
        for name in names:
            extra = catalog_extras.get(str(name))
            if not extra:
                raise ValidationError({'items': f'Invalid extra for {dish.name}.'})
            price += extra.price
            normalized['extras'].append({'name': extra.name, 'price': str(extra.price)})
        if customs.get('spiceLevel'):
            normalized['spiceLevel'] = str(customs['spiceLevel'])[:40]
        if customs.get('cookingNotes'):
            normalized['cookingNotes'] = str(customs['cookingNotes'])[:1000]
        if price < 0:
            raise ValidationError({'items': 'Invalid catalog price. Please contact the restaurant.'})
        price = money(price)
        subtotal += price * item['quantity']
        result.append({'dish': dish, 'name': dish.name, 'quantity': item['quantity'],
                       'price': price, 'station': dish.station, 'customizations': normalized})
    subtotal = money(subtotal)
    profile = checkout_policy()
    threshold = profile.free_delivery_threshold if profile else Decimal(str(getattr(settings, 'ORDER_FREE_DELIVERY_THRESHOLD', '30.00')))
    fee_value = profile.delivery_fee if profile else Decimal(str(getattr(settings, 'ORDER_DELIVERY_FEE', '2.00')))
    fee = money(fee_value) if dining_type == 'delivery' and subtotal < threshold else Decimal('0.00')
    # Menu prices include VAT; tax is disclosed, never added a second time.
    vat = profile.included_vat_percent / 100 if profile else Decimal(str(getattr(settings, 'ORDER_INCLUDED_VAT_RATE', '0.135')))
    tax = money(subtotal * vat / (1 + vat))
    return result, {'subtotal': subtotal, 'tax': tax, 'delivery_fee': fee,
                    'total_amount': money(subtotal + fee)}


def apply_promotion(totals, code, user=None, lock=False):
    from apps.engagement.models import Promotion
    code = (code or '').strip().upper()
    totals = {**totals, 'discount_amount': Decimal('0.00')}
    if not code:
        return totals, None
    queryset = Promotion.objects.all()
    if lock:
        queryset = queryset.select_for_update()
    promotion = queryset.filter(code__iexact=code, is_active=True, valid_until__gte=timezone.localdate()).first()
    if not promotion or promotion.usage_count >= promotion.usage_limit:
        raise ValidationError({'coupon_code': 'This voucher is invalid, expired or fully redeemed.'})
    if totals['subtotal'] < promotion.min_spend:
        diff = money(promotion.min_spend - totals['subtotal'])
        raise ValidationError({'coupon_code': f'Minimum food spend is €{promotion.min_spend:.2f}. Add €{diff:.2f} more to unlock this discount.'})
    if promotion.first_order_only:
        from .models import Order
        if not user or not user.is_authenticated:
            raise ValidationError({'coupon_code': 'Sign in to use this first-order voucher.'})
        if lock:
            from django.contrib.auth import get_user_model
            get_user_model().objects.select_for_update().get(pk=user.pk)
        if Order.objects.filter(customer=user).exclude(status='cancelled').exists():
            raise ValidationError({'coupon_code': 'This voucher is for your first order only.'})
    discount = money(totals['subtotal'] * promotion.discount_value / 100) if promotion.discount_type == 'percentage' else promotion.discount_value
    totals['discount_amount'] = min(discount, totals['subtotal'])
    net = totals['subtotal'] - totals['discount_amount']
    profile = checkout_policy()
    rate = profile.included_vat_percent / 100 if profile else Decimal(str(getattr(settings, 'ORDER_INCLUDED_VAT_RATE', '0.135')))
    totals['tax'] = money(net * rate / (1 + rate))
    totals['total_amount'] = money(net + totals['delivery_fee'])
    return totals, promotion
