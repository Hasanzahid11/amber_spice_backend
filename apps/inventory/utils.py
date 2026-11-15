from decimal import Decimal


def normalize_unit(unit_str: str) -> str:
    """Normalizes various spellings of units to standard canonical representations."""
    if not unit_str:
        return 'pieces'
    u = str(unit_str).strip().lower()

    # Weight representations
    if u in ['kg', 'kgs', 'kilogram', 'kilograms', 'kilo', 'kilos']:
        return 'kg'
    if u in ['g', 'gm', 'gms', 'gram', 'grams']:
        return 'g'
    if u in ['mg', 'mgs', 'milligram', 'milligrams']:
        return 'mg'
    if u in ['lb', 'lbs', 'pound', 'pounds']:
        return 'lb'
    if u in ['oz', 'ounce', 'ounces']:
        return 'oz'

    # Volume representations
    if u in ['l', 'ltr', 'ltrs', 'litre', 'litres', 'liter', 'liters']:
        return 'litre'
    if u in ['ml', 'mls', 'millilitre', 'millilitres', 'milliliter', 'milliliters']:
        return 'ml'
    if u in ['cl', 'cls', 'centilitre', 'centilitres']:
        return 'cl'
    if u in ['dl', 'dls', 'decilitre', 'decilitres']:
        return 'dl'

    # Count representations
    if u in ['pc', 'pcs', 'piece', 'pieces', 'unit', 'units', 'item', 'items', 'portion', 'portions']:
        return 'pieces'
    if u in ['pack', 'packs', 'packet', 'packets']:
        return 'packs'
    if u in ['box', 'boxes']:
        return 'boxes'
    if u in ['bag', 'bags']:
        return 'bags'
    if u in ['can', 'cans']:
        return 'cans'
    if u in ['bottle', 'bottles']:
        return 'bottles'

    return u


def convert_quantity(quantity: Decimal, from_unit: str, to_unit: str) -> Decimal:
    """
    Converts quantities between compatible units (e.g. g <-> kg, ml <-> litre).
    If units are identical or incompatible (e.g. kg <-> pieces), returns the quantity unchanged.
    """
    if quantity is None:
        return Decimal('0.000')

    q = Decimal(str(quantity))
    u_from = normalize_unit(from_unit)
    u_to = normalize_unit(to_unit)

    if u_from == u_to:
        return q

    # Weight factors relative to 1 gram
    weight_to_grams = {
        'kg': Decimal('1000'),
        'g': Decimal('1'),
        'mg': Decimal('0.001'),
        'lb': Decimal('453.592'),
        'oz': Decimal('28.3495'),
    }

    # Volume factors relative to 1 millilitre
    volume_to_ml = {
        'litre': Decimal('1000'),
        'ml': Decimal('1'),
        'cl': Decimal('10'),
        'dl': Decimal('100'),
    }

    # Weight conversion
    if u_from in weight_to_grams and u_to in weight_to_grams:
        grams = q * weight_to_grams[u_from]
        return grams / weight_to_grams[u_to]

    # Volume conversion
    if u_from in volume_to_ml and u_to in volume_to_ml:
        ml = q * volume_to_ml[u_from]
        return ml / volume_to_ml[u_to]

    # Incompatible or unit-less counts (return unchanged)
    return q

