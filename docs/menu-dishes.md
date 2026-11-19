# Dish API and creator attribution

Base path: `/api/v1/menu/dishes/`. Apply migrations with `python manage.py migrate` before using the updated API.

## Create a dish under a category

POST requires a connected account with `menu:manage`. Send the category's integer ID, a name and a positive price. The category must be active for a new dish or reassignment.

```json
{
  "category": 7,
  "name": "Chicken Biryani",
  "price": "15.50",
  "description": "Slow-cooked chicken and basmati rice",
  "station": "biryani",
  "spicyLevel": 1,
  "dietary": ["halal"],
  "prepTime": "20-25 min",
  "isAvailable": true,
  "isPopular": false,
  "isBestseller": false,
  "isSpecial": false
}
```

HTTP 201 returns the saved dish, including `id`, `category`, `category_name`, `slug`, `imageUrl`, flags, options, timestamps and `addedBy`. IDs/prices above are illustrative request values, not runtime fixtures.

| Property | Write behavior |
| --- | --- |
| `name` | Required; nonblank, max 200 characters |
| `category` | Required integer category ID; not a name or slug |
| `price` | Required decimal, minimum 0.01; 10 digits total, 2 decimal places |
| `slug` | Optional unique label, max 220 characters; generated with collision suffixes; renaming retains it |
| `description` | Optional text |
| `image` | Optional JPEG/PNG/WebP upload, up to 5 MiB, 6000 pixels per side and 25 megapixels; write only |
| `imageUrl` | Optional external HTTP/HTTPS URL, max 500 characters on write; response resolves an uploaded file's public URL |
| `station` | `biryani`, `curry`, `grill`, `breads`, `dessert` or `beverage`; default `curry` |
| `spicyLevel` | Integer 0 (non-spicy) through 3 (extra hot); default 0 |
| `dietary` | Array of `halal`, `vegetarian`, `vegan`, `gluten-free`, `dairy-free`; default empty |
| `prepTime` | Optional text, max 50 characters; model default `15-20 min` |
| `isAvailable` | Boolean, default true |
| `isPopular`, `isBestseller`, `isSpecial` | Booleans, default false |
| `id`, `category_name`, `rating`, `ordersCount`, `portionOptions`, `extraOptions`, `created_at`, `addedBy` | Read only. New dishes start with rating/order count 0. Option configuration is not part of this create form. |

Use `multipart/form-data` to upload `image` along with other properties. Send `dietary` as a JSON array string, e.g. `["halal"]` or `[]`, when using multipart. Let the HTTP client set the multipart boundary. The admin service handles this automatically.

For local Windows development, run `./start-dev.ps1` from the backend folder. It enables development media serving without changing `.env`. Restart an existing server after module/package refactors; verify its live schema includes the binary `image` request field. A dish created through an old process without that field has no saved image and needs its image selected again in Edit Dish.

PATCH `/api/v1/menu/dishes/{id}/` edits supplied fields. An unchanged uploaded image is retained when both image fields are omitted. Send another `image` to replace it, `{"image": null}` to clear it, or `imageUrl` to switch to an external URL. Replaced files are deleted after commit. Sending both a nonempty file and URL is rejected.

## Lists and availability

GET is public for dishes under active categories. Menu managers can also inspect hidden categories. Public consumers request `?is_available=true`; `?category=7` and `?category__slug=biryani` filter by category. Search, ordering and pagination follow the existing DRF configuration. The admin and website follow all pages.

PATCH `/api/v1/menu/dishes/{id}/toggle-availability/` accepts `{"is_available": false}`. It requires `menu:toggle_availability`, validates boolean input and preserves the creator. It returns `id`, `name`, `message` and `is_available`; the admin then reads the saved dish. Omitting the property toggles the current value.

Category counts and popular-dish caches are invalidated after menu API writes. An available new dish appears on the customer menu after loading/refreshing. Unavailable dishes remain visible in admin for maintenance.

## Added by

Both category and dish creation set `created_by` from the authenticated request user. `addedBy` is a read-only response property:

```json
{"id": 12, "name": "Restaurant Manager", "role": "manager"}
```

This object is visible to menu managers. Public and other users receive `addedBy: null`; staff emails and other account fields are not published. Category/popular caches separate these audiences. Client-supplied `created_by` or `addedBy` cannot choose or change a creator. Editing and availability changes retain the original creator. Django admin creation also records its request user.

Preexisting/imported records have null creators, displayed as **Added by: Not recorded**. No historical creator is guessed. If a creator account is deleted, the menu record is retained and its creator relation becomes null.

## Admin flow and verification

Products → Add New Dish selects a real category and saves through POST. Product cards use API data and show Added by; Edit and availability switches call the backend. The category tabs also show Added by. There is no local dish store, generated sample ID or mock menu fallback.

Tests cover category/dish attribution, spoof prevention, creator retention, permissions, active-category validation, prices/slugs/dietary/spice, real image storage/replacement, customer visibility, cache separation and Django admin attribution. Frontend tests cover upload/create, reload, edit, availability, failures and empty results.
