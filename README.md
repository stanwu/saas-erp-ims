# ERP IMS

A minimal ERP/IMS SaaS MVP built with FastAPI, Jinja2, and SQLite3.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
export ERP_IMS_SECRET_KEY="change-me"
export ERP_IMS_ADMIN_USERNAME="admin"
export ERP_IMS_ADMIN_EMAIL="admin@example.com"
export ERP_IMS_ADMIN_PASSWORD="admin12345"
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Default behavior

- SQLite database file defaults to `erp_ims.db` in the project root.
- On first startup, the app creates tables and seeds the initial admin account.
- Admin can manage users, products, and inventory movements.
- Staff can view products and create inventory movements.

## Tests

```bash
pytest
```
