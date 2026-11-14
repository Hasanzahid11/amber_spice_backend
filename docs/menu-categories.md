# Menu Category API

Base URL: `http://127.0.0.1:8000/api/v1/menu/categories/`

This extends the existing category resource with file uploads. Apply the nullable image-field migration with `python manage.py migrate` before running the updated backend. Existing categories and external image URLs are preserved.

## Endpoints and access

| Method | Path | Access | Result |
| --- | --- | --- | --- |
| GET | `/api/v1/menu/categories/` | Public | Paginated active categories; menu managers also see inactive categories |
| POST | `/api/v1/menu/categories/` | `menu:manage` | Create category; HTTP 201 |
| GET | `/api/v1/menu/categories/{id}/` | Public for active category; menu managers for inactive too | Category detail |
| PUT | `/api/v1/menu/categories/{id}/` | `menu:manage` | Full update; name required |
| PATCH | `/api/v1/menu/categories/{id}/` | `menu:manage` | Update supplied properties only |
| DELETE | `/api/v1/menu/categories/{id}/` | `menu:manage` | Archive (`is_active=false`); HTTP 204, no response body |

For protected requests, send `Authorization: Bearer <access_token>`. Use JSON for ordinary properties or `multipart/form-data` when uploading a file. Let the HTTP client set the multipart boundary. Menu management follows existing dynamic permissions, including approved per-user grants/revocations. The existing owner/admin/manager policy remains in effect. Being logged in as a customer or kitchen staff alone does not permit category writes.

Archive preserves the category and its dishes. The archived category and its dishes are excluded from public category/menu/detail/popular/bestseller reads. A menu manager can retrieve it and reactivate it with PATCH. This avoids the previous API DELETE behavior cascading through related dishes. Direct database/Django-admin operations are outside this API's archive contract.

## Properties

| Property | Type | Required on create | Writable | Default / meaning |
| --- | --- | --- | --- | --- |
| `id` | integer | No | No | Database-generated category ID; use this as a dish's `category` foreign key |
| `name` | string, max 100 characters | **Yes** | Yes | Display name; surrounding whitespace trimmed; empty and case-insensitive duplicate names rejected by API validation |
| `slug` | string, max 120 characters | No | Yes | Unique URL/filter label; generated from name if omitted/blank on create; supplied slugs normalized to lowercase |
| `image` | JPEG, PNG or WebP file, or null | No | Write only | Upload using multipart; max 5 MiB, 6000 pixels per side and 25 megapixels; JSON null clears an existing image |
| `imageUrl` | HTTP/HTTPS URL string, or null | No | Yes | Response contains the uploaded file's public URL or the external URL. External URL writes are limited to 500 characters; empty string/null clears the image |
| `description` | string | No | Yes | Category description; default empty string |
| `order` | integer >= 0 | No | Yes | Display position; default 0; smaller values appear first |
| `is_active` | boolean | No | Yes | Public visibility; default true |
| `dishCount` | integer | No | No | Number of related dishes with `is_available=true` |
| `created_at` | ISO 8601 timestamp | No | No | Server-generated creation timestamp |

Only `name` is required on POST. On PATCH, supply only fields being changed. The spelling/casing above is intentional and retains existing client field names.

Renaming a category does not automatically change an existing slug. Supplying a blank slug on update retains the existing slug. To intentionally change it, send a new unique valid slug. Slugs accept letters/numbers/underscores/hyphens; generated collisions receive a suffix such as `chef-special-2`. Names that do not produce an ASCII slug receive a nonempty generated `category` slug, with a suffix where needed; callers can provide their preferred slug explicitly.

Upload `image` or provide `imageUrl`; supplying both nonempty values returns HTTP 400. Uploaded content is validated as an actual image, and its extension follows its detected format. Files receive unique names under `MEDIA_ROOT/menu/categories/`. Responses keep the existing `imageUrl` property, so consumers do not need a new display field. The upload-only `image` field never appears in responses.

The admin supports **Products → Add Category → Choose Image**, including local preview, replace/remove controls and validation. The file uploads when Save Category is pressed. An external image URL remains optional.

## File upload example

POST `/api/v1/menu/categories/` as multipart form data:

```javascript
const body = new FormData();
body.append('name', 'Seafood');
body.append('image', fileInput.files[0]);
body.append('order', '2');
body.append('is_active', 'true');

const response = await fetch('/api/v1/menu/categories/', {
  method: 'POST',
  headers: { Authorization: `Bearer ${accessToken}` },
  body,
});
const category = await response.json();
// category.imageUrl: http://127.0.0.1:8000/media/menu/categories/<unique-name>.png
```

The same multipart fields work with PATCH to replace an uploaded image. JSON PATCH with `{"image": null}` clears it. Setting `imageUrl` replaces any uploaded file with the external URL. Replaced/cleared files are deleted after the database transaction commits; archiving keeps the image for restoration.

Django serves `/media/` during local development with DEBUG enabled. Production hosting must serve `MEDIA_ROOT` at `MEDIA_URL`, or configure Django's default storage for an external media service.

## Create example

POST `/api/v1/menu/categories/`

```json
{
  "name": "Biryani",
  "description": "Our signature dum biryanis",
  "imageUrl": "https://example.com/images/biryani.webp",
  "order": 1,
  "is_active": true
}
```

Example HTTP 201 response (ID/time are illustrative):

```json
{
  "id": 7,
  "name": "Biryani",
  "slug": "biryani",
  "dishCount": 0,
  "imageUrl": "https://example.com/images/biryani.webp",
  "description": "Our signature dum biryanis",
  "order": 1,
  "is_active": true,
  "created_at": "2026-11-14T12:00:00Z"
}
```

The smallest valid create body is `{"name": "Biryani"}`. If that name is already present, validation returns HTTP 400 with a `name` error.

## List, search and filtering

| Query | Meaning |
| --- | --- |
| `?search=biryani` | Search name/description |
| `?slug=biryani` | Exact slug filter |
| `?is_active=true` | Active categories |
| `?is_active=false` | Inactive categories for menu managers; public users receive an empty result |
| `?ordering=order,name` | Sort by position/name |
| `?ordering=-created_at` | Newest first |
| `?page=2` | Next pagination page |

Default ordering: `order`, then `name`, then ID for a stable default order. Default page size follows backend configuration, currently 20.

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 7,
      "name": "Biryani",
      "slug": "biryani",
      "dishCount": 0,
      "imageUrl": null,
      "description": "",
      "order": 1,
      "is_active": true,
      "created_at": "2026-11-14T12:00:00Z"
    }
  ]
}
```

Inactive detail is HTTP 404 for public/non-manager requests. List caches are separated by request URL/query and management visibility. Category API writes invalidate category list variants and popular dishes. Dish API writes/availability changes invalidate category counts. Cached response lifetime remains 15 minutes; external direct database writes do not invoke these API invalidation hooks.

## Edit, hide and restore

PATCH `/api/v1/menu/categories/7/` with `{"name": "Royal Biryani", "order": 2}` updates the supplied fields and preserves the slug.

PATCH with `{"is_active": false}` hides it. DELETE has the same archive effect. PATCH with `{"is_active": true}` restores it. A manager's default list includes inactive entries, so the admin should use `is_active` to show an archived status or filter.

## Category → dish → customer flow

1. Admin creates/loads category using this API.
2. Admin's dish request to `/api/v1/menu/dishes/` supplies the returned integer ID as `category`, not the category name.
3. Customer category tabs use `name`, `slug`, `imageUrl`, `order` and `dishCount` from `results`.
4. Customer dish lookup can use `/api/v1/menu/dishes/?category=7` or `?category__slug=biryani`.
5. Customer public dish reads exclude archived categories. Menu managers can still inspect their dishes for maintenance/restoration.

The admin category list, creation form and dish category dropdown are integrated. Customer home/mobile/menu categories and dishes also load from the backend, without a mock catalog fallback. Admin dish publishing remains separate integration work; its existing local writes are not a completed API integration.

## Validation and verification

- Duplicate names/slugs, blank names, invalid URLs and negative ordering return HTTP 400 field errors.
- Corrupt, unsupported, oversized or excessive-dimension images return HTTP 400 image-field errors before file storage. Upload tests cover real file persistence, public URLs, replacement/cleanup, archive retention and unauthorized writes.
- Writes require menu-management permission. Public reads never gain inactive visibility through a cached manager response.
- Read-only IDs/counts/timestamps cannot be overridden by requests.
- API archive preserves related dishes, hides them publicly and can be reversed by an authorized update.
- Regression coverage includes category CRUD/validation, filtering/pagination/cache separation, dynamic permission grants, archive/restore and dish visibility/count invalidation, plus the existing accounts/profile suites.
- Tests use an isolated SQLite test database, memory cache and a test-only fast password hasher for the combined regression run. Production password hashing/cache configuration is unchanged.

Interactive API documentation: `/api/docs/`. Machine-readable schema: `/api/schema/`.
