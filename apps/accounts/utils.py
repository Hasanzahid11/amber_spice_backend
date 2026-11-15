import re
from typing import Optional, Set


def normalize_phone_number(phone: str) -> str:
    """
    Normalizes phone numbers with first-class support for Irish phone numbers:
    - Strips whitespace, hyphens, parentheses, and dots.
    - Resolves Irish mobile (08x xxx xxxx, 10 digits) to standard E.164 (+3538xxxxxxxx).
    - Resolves Irish landlines (01..., 02x..., etc.) to +353...
    - Converts 00353 and 353 prefixes to +353.
    - Retains international numbers starting with '+' or '00'.
    """
    if not phone:
        return ''

    cleaned = phone.strip()
    # Strip spaces, dashes, dots, parentheses
    cleaned = re.sub(r'[\s\-\(\)\.]+', '', cleaned)

    # 00 prefix -> +
    if cleaned.startswith('00'):
        cleaned = '+' + cleaned[2:]

    # Erroneous +3530... -> +353...
    if cleaned.startswith('+3530'):
        cleaned = '+353' + cleaned[5:]

    # Irish mobile (083, 085, 086, 087, 089) or landlines (01, 021, etc.) starting with 0
    # Irish mobile is 10 digits; landlines are 9 to 10 digits
    if cleaned.startswith('0') and len(cleaned) in (9, 10) and cleaned[1:].isdigit():
        cleaned = '+353' + cleaned[1:]

    # Irish number starting with 353 without '+'
    elif cleaned.startswith('353') and not cleaned.startswith('+') and cleaned.isdigit():
        cleaned = '+' + cleaned

    # 9-digit Irish mobile without leading 0 (e.g. 871234567)
    elif len(cleaned) == 9 and cleaned.startswith(('83', '85', '86', '87', '89')) and cleaned.isdigit():
        cleaned = '+353' + cleaned

    return cleaned


def validate_phone_number(phone: str) -> str:
    """
    Validates that the provided phone number is well-formed and returns the normalized string.
    Raises serializers.ValidationError if invalid.
    """
    try:
        from rest_framework import serializers
        exc_class = serializers.ValidationError
    except ImportError:
        exc_class = ValueError

    if not phone or not phone.strip():
        raise exc_class("Phone number cannot be empty.")

    raw = phone.strip()
    # Check for invalid characters
    if not re.match(r'^[+0-9\s\-\(\)\.]+$', raw):
        raise exc_class(
            "Phone number contains invalid characters. Use digits, spaces, '+', '-', or parentheses."
        )

    digits = re.sub(r'\D', '', raw)
    if len(digits) < 7:
        raise exc_class("Phone number is too short (minimum 7 digits).")
    if len(digits) > 15:
        raise exc_class("Phone number is too long (maximum 15 digits).")

    normalized = normalize_phone_number(raw)
    return normalized


def get_phone_lookup_variants(phone: str) -> list[str]:
    """
    Generates plausible variations of a phone number to match against stored database records.
    Handles raw format, normalized E.164, local Irish format (08x...), spaced format (+353 87 123 4567), etc.
    """
    if not phone:
        return []

    raw = phone.strip()
    normalized = normalize_phone_number(raw)
    digits = re.sub(r'\D', '', raw)

    variants: Set[str] = {raw, normalized, digits}

    # If starts with +353
    if normalized.startswith('+353'):
        local_part = normalized[4:]  # e.g. 871234567
        local_with_zero = '0' + local_part
        variants.add(local_with_zero)
        variants.add('353' + local_part)
        variants.add('00353' + local_part)

        # Formatted variants: +353 87 123 4567 and 087 123 4567
        if len(local_part) == 9:
            prefix = local_part[:2]       # 87
            mid = local_part[2:5]         # 123
            end = local_part[5:]          # 4567
            variants.add(f"+353 {prefix} {mid} {end}")
            variants.add(f"+353{prefix}{mid}{end}")
            variants.add(f"0{prefix} {mid} {end}")
            variants.add(f"0{prefix}-{mid}-{end}")

    # If starts with Irish 0 (e.g. 0871234567)
    elif raw.startswith('0') and len(digits) in (9, 10):
        intl = '+353' + digits[1:]
        variants.add(intl)
        variants.add('353' + digits[1:])
        variants.add('00353' + digits[1:])
        if len(digits) == 10:
            prefix = digits[1:3]
            mid = digits[3:6]
            end = digits[6:]
            variants.add(f"+353 {prefix} {mid} {end}")
            variants.add(f"{digits[:3]} {mid} {end}")

    # Clean empty strings
    return [v for v in variants if v]


def find_user_by_phone(phone_input: str):
    """
    Searches for an active User matching phone_input across all common representations.
    """
    if not phone_input or not phone_input.strip():
        return None

    User = get_user_model()
    raw = phone_input.strip()
    variants = get_phone_lookup_variants(raw)

    # 1. Fast indexed lookup against all variants
    user = User.objects.filter(phone__in=variants).first()
    if user:
        return user

    # 2. Case-insensitive / exact stripped lookup
    user = User.objects.filter(phone__iexact=raw).first()
    if user:
        return user

    # 3. Cleaned digits match (fallback for unusual DB formatting)
    raw_digits = re.sub(r'\D', '', raw)
    if len(raw_digits) >= 7:
        candidate_digits = {raw_digits}
        if raw_digits.startswith('0'):
            candidate_digits.add('353' + raw_digits[1:])
        elif raw_digits.startswith('353'):
            candidate_digits.add('0' + raw_digits[3:])

        for u in User.objects.exclude(phone__isnull=True).exclude(phone=''):
            u_digits = re.sub(r'\D', '', u.phone or '')
            if u_digits and u_digits in candidate_digits:
                return u

    return None
