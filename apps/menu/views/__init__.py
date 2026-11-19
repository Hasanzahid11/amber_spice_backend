"""Public viewsets registered by the menu router."""
from .category import CategoryViewSet
from .dish import DishViewSet

__all__ = ['CategoryViewSet', 'DishViewSet']
