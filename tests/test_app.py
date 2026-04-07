from pathlib import Path
import os

from fastapi.testclient import TestClient


TEST_DB = Path(__file__).resolve().parent / "test_erp_ims.db"
os.environ["ERP_IMS_DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["ERP_IMS_SECRET_KEY"] = "test-secret"
os.environ["ERP_IMS_ADMIN_USERNAME"] = "admin"
os.environ["ERP_IMS_ADMIN_EMAIL"] = "admin@example.com"
os.environ["ERP_IMS_ADMIN_PASSWORD"] = "admin12345"

from app.main import app  # noqa: E402


def setup_module():
    if TEST_DB.exists():
        TEST_DB.unlink()


def teardown_module():
    if TEST_DB.exists():
        TEST_DB.unlink()


def login(client: TestClient):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin12345"},
        follow_redirects=False,
    )


def test_seeded_admin_login_and_dashboard():
    with TestClient(app) as client:
        response = login(client)
        assert response.status_code == 303
        dashboard = client.get("/dashboard")
        assert dashboard.status_code == 200
        assert "Dashboard" in dashboard.text


def test_admin_can_create_product_and_movement():
    with TestClient(app) as client:
        login(client)
        response = client.post(
            "/products/new",
            data={
                "sku": "SKU-001",
                "name": "Widget",
                "description": "Primary stock item",
                "unit": "pcs",
                "is_active": "on",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        movement = client.post(
            "/movements/new",
            data={
                "product_id": 1,
                "movement_type": "in",
                "quantity": 5,
                "note": "Initial stock",
            },
            follow_redirects=False,
        )
        assert movement.status_code == 303

        product_page = client.get("/products/1")
        assert product_page.status_code == 200
        assert "Stock 5" in product_page.text


def test_insufficient_stock_is_blocked():
    with TestClient(app) as client:
        login(client)
        response = client.post(
            "/movements/new",
            data={
                "product_id": 1,
                "movement_type": "out",
                "quantity": 99,
                "note": "Bad issue",
            },
        )
        assert response.status_code == 400
        assert "Insufficient stock" in response.text
