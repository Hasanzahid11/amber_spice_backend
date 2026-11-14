"""Shared cache keys and invalidation for category and dish writes."""
from django.core.cache import cache

CACHE_KEY_CATEGORIES = 'menu:categories:v2'
CACHE_KEY_POPULAR = 'menu:popular_dishes:v2'
CACHE_TIMEOUT = 60 * 15  # 15 minutes


def invalidate_menu_cache():
    cache.delete(CACHE_KEY_CATEGORIES)
    cache.delete(CACHE_KEY_POPULAR)
