"""Register menu models when Django autodiscovers this admin package."""
from .category import CategoryAdmin
from .dish import DishAdmin, DishExtraOptionInline, DishPortionOptionInline

__all__ = ['CategoryAdmin', 'DishAdmin', 'DishExtraOptionInline', 'DishPortionOptionInline']
