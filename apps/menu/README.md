# Menu app structure

Category, dish and option code lives in separate modules within each Django layer.

```text
apps/menu/
|-- models/
|   |-- category.py          # Category fields, image path, slug and dish count
|   |-- dish.py              # Dish fields and category relationship
|   |-- options.py           # Portion and extra option models
|   `-- __init__.py          # Stable public model imports
|-- serializers/
|   |-- category.py          # Category validation and image upload/cleanup
|   |-- dish.py              # Dish API fields and nested options
|   |-- options.py           # Portion and extra option representations
|   |-- images.py            # Shared upload validation and file cleanup
|   |-- attribution.py       # Read-only creator representation
|   `-- __init__.py
|-- views/
|   |-- category.py          # Category CRUD, visibility, archive and list cache
|   |-- dish.py              # Dish CRUD, popular/bestsellers and availability
|   `-- __init__.py
|-- services/
|   |-- cache.py             # Shared menu cache keys and invalidation
|   `-- __init__.py
|-- admin/
|   |-- category.py          # Django category admin
|   |-- dish.py              # Django dish admin and option inlines
|   `-- __init__.py
|-- tests/
|   |-- test_categories.py   # Category API and related dish/cache behavior
|   |-- test_category_images.py # Upload validation, persistence and cleanup
|   |-- test_dishes.py       # Dish CRUD, creators, permissions and public visibility
|   `-- __init__.py
|-- migrations/              # Existing database migration history
|-- management/commands/     # Restaurant seed command
|-- urls.py                  # Category/dish router registration
|-- apps.py                  # Django app configuration
`-- __init__.py
```

Requests go through `urls.py` to the matching viewset, then through its serializer to the model. Both viewsets use `services/cache.py` to invalidate category and popular-dish caches when menu data changes. Django discovers the `admin` package and its registrations automatically.

Existing imports such as `from apps.menu.models import Category, Dish` and `from apps.menu.views import CategoryViewSet` remain supported through package exports. The historical `apps.menu.models.category_image_path` migration reference also remains available. This folder refactor does not change database tables or API routes and requires no additional migration.

Run from the backend root:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test apps.menu
```

For the category API contract, see [Menu Category API](../../docs/menu-categories.md).
