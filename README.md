# 🍽️ Restaurant Management Backend (Amber & Spice)

High-performance, scalable, gold-standard REST API backend for Restaurant Management System built with **Django**, **Django REST Framework (DRF)**, **PostgreSQL**, **Redis**, and **Celery**.

Complies strictly with **Section 18: User Roles & Permissions** from the project specification.

---

## 🚀 Tech Stack

- **Framework:** Python 3.11+ / 3.14, Django 6.x
- **API Engine:** Django REST Framework (DRF) + `djangorestframework-simplejwt`
- **Database:** PostgreSQL (with `psycopg` 3 modern binary driver) & SQLite development fallback
- **Caching & Broker:** Redis (`django-redis` & `redis-py`)
- **Background Tasks:** Celery
- **API Documentation:** OpenAPI 3.0 / Swagger UI (`drf-spectacular`)
- **Containerization:** Docker & Docker Compose

---

## 🛡️ Section 18: User Roles & Permissions Architecture

The system implements a granular, production-ready Role-Based Access Control (RBAC) system with **dynamically configurable permissions**:

| Role | Access Level / Module Access | Sample Credentials |
| :--- | :--- | :--- |
| **Owner / Admin** | **Full Access**: All modules, staff management, financials, and runtime permission configuration. | `admin` / `admin123` |
| **Manager** | **Orders, Menu, Inventory, Reports & Staff**: Manages items, restocks, analyzes revenue, schedules staff. | `manager_sarah` / `manager123` |
| **Kitchen Staff** | **Kitchen Orders Only**: Dedicated KDS view (pending, preparing, ready) & item out-of-stock toggle. | `chef_rajesh` / `kitchen123` |
| **Delivery Staff** | **Assigned Deliveries Only**: View assigned orders & update delivery status (out_for_delivery, delivered). | `delivery_dave` / `delivery123` |
| **Cashier / Front** | **Orders & Front-Facing**: POS order creation, customer billing, and table/reservation management. | `cashier_linda` / `cashier123` |
| **Customer** | **Customer Operations**: Menu browsing, self-ordering, booking reservations, viewing order history. | `customer_mark` / `customer123` |

### ⚙️ Configurable Permissions Feature
Permissions are **not hardcoded**. Administrators can modify role permissions dynamically at runtime via the API or Admin panel (`/api/v1/auth/roles-config/`), and override permissions per individual staff member if needed (`/api/v1/auth/staff/<id>/permissions/`).

---

## 📂 Project Structure

```text
resturent_backend/
├── config/                  # Django project root (settings, urls, wsgi, asgi, celery)
├── apps/
│   ├── accounts/            # Users, JWT Auth, RBAC, Configurable Permissions, Staff & Customers
│   ├── menu/                # Categories, Dishes, Portions, Extras, Out-of-Stock Toggle
│   ├── orders/              # Orders, OrderItems, Kitchen Station KDS, Delivery tracking
│   ├── reservations/        # Tables, Reservations, Seating allocation
│   ├── inventory/           # Stock items, Categories, Thresholds, Low-stock alerts
│   ├── staff/               # Staff directory, Roles, Shifts, Station assignments
│   └── analytics/           # Business metrics, Daily revenue, Top-selling dishes
├── Dockerfile               # Production-ready Docker container configuration
├── docker-compose.yml       # Multi-container orchestration (PostgreSQL, Redis, Django, Celery)
├── requirements.txt         # Pinned production dependencies
├── .env.example             # Environment configuration template
└── manage.py
```

---

## ⚡ Quick Start

### Option 1: Run with Docker Compose (Recommended - PostgreSQL + Redis + Celery + Django)

Make sure Docker is running on your machine, then run:

```bash
docker compose up --build
```

The system will automatically:
1. Start PostgreSQL 16 on port `5432`.
2. Start Redis 7 on port `6379`.
3. Apply database migrations.
4. Seed the database with Section 18 roles, staff accounts, dishes, tables, and inventory.
5. Launch the backend API server at `http://localhost:8000`.
6. Launch the Celery worker for asynchronous background tasks.

---

### Option 2: Run Locally (Python Virtual Environment)

1. **Activate virtual environment:**
   ```bash
   cd resturent_backend
   .\venv\Scripts\activate   # Windows
   # or source venv/bin/activate (Linux/Mac)
   ```

2. **Configure `.env` file:**
   Copy `.env.example` to `.env` and configure your database and Redis URLs.
   *(Set `USE_SQLITE=True` for quick zero-config local testing without external servers).*

3. **Apply migrations:**
   ```bash
   python manage.py migrate
   ```

4. **Seed initial restaurant data & Section 18 role accounts:**
   ```bash
   python manage.py seed_restaurant_data
   ```

5. **Run tests to verify:**
   ```bash
   python manage.py test apps.accounts
   ```

6. **Start development server:**
   ```bash
   python manage.py runserver
   ```

---

## 📖 API Documentation & Swagger UI

Once the server is running, explore the interactive documentation and try out endpoints:

- **Swagger UI:** [http://127.0.0.1:8000/api/docs/](http://127.0.0.1:8000/api/docs/)
- **ReDoc:** [http://127.0.0.1:8000/api/redoc/](http://127.0.0.1:8000/api/redoc/)
- **OpenAPI Schema:** [http://127.0.0.1:8000/api/schema/](http://127.0.0.1:8000/api/schema/)
- **Django Admin:** [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

---

## 🔑 Key API Endpoints

### 🔐 Authentication & Roles (`/api/v1/auth/`)
- `POST /api/v1/auth/register/` - Customer registration (auto-generates JWT).
- `POST /api/v1/auth/login/` - Login with username OR email. Returns tokens + user permissions matrix.
- `GET /api/v1/auth/me/` - Retrieve current user profile and effective permissions list.
- `GET/POST /api/v1/auth/staff/` - Manage staff accounts (Admin / Manager only).
- `GET/PATCH /api/v1/auth/roles-config/` - View and configure permissions per role dynamically (Admin only).

### 🍲 Menu Management (`/api/v1/menu/`)
- `GET /api/v1/menu/categories/` - Categories (Redis cached).
- `GET /api/v1/menu/dishes/` - Menu items.
- `PATCH /api/v1/menu/dishes/<id>/toggle-availability/` - Mark item available/unavailable (Kitchen & Cashier staff).

### 📦 Orders & Kitchen Display (`/api/v1/orders/`)
- `POST /api/v1/orders/` - Place order (Cashier / Customer).
- `GET /api/v1/orders/kitchen/` - Kitchen Display System (KDS) filtered by station (Kitchen staff).
- `GET /api/v1/orders/deliveries/` - Assigned deliveries view (Delivery staff).
- `PATCH /api/v1/orders/<id>/update_status/` - Role-enforced order status updates.

### 📊 Analytics & Reports (`/api/v1/analytics/`)
- `GET /api/v1/analytics/summary/` - Real-time revenue, orders, tables, and top dishes (Manager & Admin only, Redis cached).

## Menu Category API

See [Menu Category API](docs/menu-categories.md) for request/response properties, create/update examples, permissions, search/filter/pagination and archive/restore behavior.

See [Menu app structure](apps/menu/README.md) for the models, serializers, views, services, admin and test folders.

