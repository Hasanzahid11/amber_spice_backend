"""Shared cache keys and invalidation for category and dish writes."""
from hashlib import sha256
from uuid import uuid4

from django.core.cache import cache

CACHE_KEY_CATEGORIES = 'menu:categories:v3'
CACHE_KEY_POPULAR = 'menu:popular_dishes:v3'
CACHE_TIMEOUT = 60 * 15  # 15 minutes


def invalidate_menu_cache():
    cache.delete(CACHE_KEY_CATEGORIES)
    cache.delete(CACHE_KEY_POPULAR)


def popular_cache_key(request):
    generation = cache.get_or_set(CACHE_KEY_POPULAR, lambda: uuid4().hex, timeout=None)
    audience = 'manage' if request.user.is_authenticated and request.user.has_restaurant_permission('menu:manage') else 'public'
    uri_hash = sha256(request.build_absolute_uri().encode()).hexdigest()
    return f'{CACHE_KEY_POPULAR}:{generation}:{audience}:{uri_hash}'
