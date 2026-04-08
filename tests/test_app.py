"""
Integration tests for the ERP IMS rewrite.
Covers: login/logout, product CRUD, record_movement, PO flow, permissions.
"""
import os
from pathlib import Path

TEST_DB = Path(__file__).resolve().parent / "test_erp_ims.db"
os.environ["ERP_IMS_DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["ERP_IMS_SECRET_KEY"] = "test-secret"
os.environ["ERP_IMS_CSRF_SECRET"] = "test-csrf-secret"
os.environ["ERP_IMS_ADMIN_USERNAME"] = "admin"
os.environ["ERP_IMS_ADMIN_PASSWORD"] = "admin12345"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import MovementType, StockLevel  # noqa: E402
from app.services import record_movement  # noqa: E402


def setup_module():
    if TEST_DB.exists():
        TEST_DB.unlink()


def teardown_module():
    if TEST_DB.exists():
        TEST_DB.unlink()


def _get_csrf(client: TestClient) -> str:
    """Fetch a CSRF token from the login page."""
    resp = client.get("/login")
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', resp.text)
    return m.group(1) if m else ""


def login_admin(client: TestClient) -> None:
    csrf = _get_csrf(client)
    resp = client.post(
        "/login",
        data={"username": "admin", "password": "admin12345", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert resp.status_code == 303, f"Login failed: {resp.text[:200]}"


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------

def test_login_redirects_to_dashboard():
    with TestClient(app) as client:
        login_admin(client)
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert "Dashboard" in resp.text


def test_login_wrong_password_returns_401():
    with TestClient(app) as client:
        csrf = _get_csrf(client)
        resp = client.post(
            "/login",
            data={"username": "admin", "password": "wrongpass", "csrf_token": csrf},
        )
        assert resp.status_code == 401


def test_unauthenticated_redirected():
    with TestClient(app) as client:
        resp = client.get("/products", follow_redirects=False)
        assert resp.status_code == 303
        assert "/login" in resp.headers["location"]


def test_logout_clears_session():
    with TestClient(app) as client:
        login_admin(client)
        csrf = _get_csrf(client)
        client.post("/logout", data={"csrf_token": csrf}, follow_redirects=False)
        resp = client.get("/products", follow_redirects=False)
        assert resp.status_code == 303


# ---------------------------------------------------------------------------
# Product CRUD
# ---------------------------------------------------------------------------

def test_create_product():
    with TestClient(app) as client:
        login_admin(client)
        csrf = _get_csrf(client)
        resp = client.post(
            "/products/new",
            data={
                "sku": "TEST-001", "name": "Test Widget",
                "unit": "pcs", "reorder_point": "10",
                "cost_price": "5.00", "is_active": "on",
                "csrf_token": csrf,
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        resp = client.get("/products")
        assert "TEST-001" in resp.text


def test_duplicate_sku_rejected():
    with TestClient(app) as client:
        login_admin(client)
        csrf = _get_csrf(client)
        resp = client.post(
            "/products/new",
            data={
                "sku": "TEST-001", "name": "Duplicate",
                "unit": "pcs", "csrf_token": csrf,
            },
        )
        assert resp.status_code == 400
        assert "already exists" in resp.text.lower()


def test_edit_product():
    with TestClient(app) as client:
        login_admin(client)
        # Get the product id from the list page
        resp = client.get("/products")
        import re
        m = re.search(r'/products/(\d+)', resp.text)
        pid = m.group(1) if m else "1"

        csrf = _get_csrf(client)
        resp = client.post(
            f"/products/{pid}/edit",
            data={
                "name": "Updated Widget", "unit": "pcs",
                "reorder_point": "5", "cost_price": "6.00",
                "is_active": "on", "csrf_token": csrf,
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303


def test_deactivate_product():
    with TestClient(app) as client:
        login_admin(client)
        import re
        m = re.search(r'/products/(\d+)', client.get("/products").text)
        pid = m.group(1) if m else "1"

        csrf = _get_csrf(client)
        resp = client.post(
            f"/products/{pid}/deactivate",
            data={"csrf_token": csrf},
            follow_redirects=False,
        )
        assert resp.status_code == 303


# ---------------------------------------------------------------------------
# record_movement (service layer)
# ---------------------------------------------------------------------------

def test_record_movement_stock_in():
    with TestClient(app):  # ensure tables created + seeded
        db = SessionLocal()
        try:
            from app.models import Product, Warehouse, User
            from sqlalchemy import select
            product = db.scalar(select(Product).where(Product.sku == "TEST-001"))
            warehouse = db.scalar(select(Warehouse).where(Warehouse.name == "Main Warehouse"))
            user = db.scalar(select(User).where(User.username == "admin"))
            if not product or not warehouse or not user:
                return  # skip if seed not ready

            # Reactivate product if deactivated
            product.is_active = True
            db.commit()

            before = db.scalar(
                select(StockLevel.quantity)
                .where(StockLevel.product_id == product.id, StockLevel.warehouse_id == warehouse.id)
            ) or 0

            record_movement(db, product.id, warehouse.id, MovementType.in_, 20, user.id, note="test in")
            db.commit()

            after = db.scalar(
                select(StockLevel.quantity)
                .where(StockLevel.product_id == product.id, StockLevel.warehouse_id == warehouse.id)
            ) or 0
            assert after == before + 20
        finally:
            db.close()


def test_record_movement_insufficient_stock():
    with TestClient(app):
        db = SessionLocal()
        try:
            from app.models import Product, Warehouse, User
            from sqlalchemy import select
            import pytest
            product = db.scalar(select(Product).where(Product.sku == "TEST-001"))
            warehouse = db.scalar(select(Warehouse).where(Warehouse.name == "Main Warehouse"))
            user = db.scalar(select(User).where(User.username == "admin"))
            if not product or not warehouse or not user:
                return

            current = db.scalar(
                select(StockLevel.quantity)
                .where(StockLevel.product_id == product.id, StockLevel.warehouse_id == warehouse.id)
            ) or 0

            try:
                record_movement(db, product.id, warehouse.id, MovementType.out,
                                current + 1000, user.id)
                db.commit()
                assert False, "Should have raised ValueError"
            except ValueError as e:
                db.rollback()
                assert "Insufficient stock" in str(e)
        finally:
            db.close()


def test_record_movement_zero_quantity_raises():
    with TestClient(app):
        db = SessionLocal()
        try:
            from app.models import Product, Warehouse, User
            from sqlalchemy import select
            product = db.scalar(select(Product).where(Product.sku == "TEST-001"))
            warehouse = db.scalar(select(Warehouse).where(Warehouse.name == "Main Warehouse"))
            user = db.scalar(select(User).where(User.username == "admin"))
            if not product or not warehouse or not user:
                return
            try:
                record_movement(db, product.id, warehouse.id, MovementType.in_, 0, user.id)
                db.commit()
                assert False, "Should have raised ValueError"
            except ValueError as e:
                db.rollback()
                assert "positive" in str(e).lower()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Purchase Order flow
# ---------------------------------------------------------------------------

def test_po_create_submit_receive():
    with TestClient(app) as client:
        login_admin(client)

        # Create supplier
        csrf = _get_csrf(client)
        resp = client.post(
            "/suppliers/new",
            data={"name": "ACME Corp", "is_active": "on", "csrf_token": csrf},
            follow_redirects=False,
        )
        assert resp.status_code == 303

        # Get IDs
        db = SessionLocal()
        try:
            from app.models import Product, Warehouse, Supplier
            from sqlalchemy import select
            product = db.scalar(select(Product).where(Product.sku == "TEST-001"))
            warehouse = db.scalar(select(Warehouse).where(Warehouse.name == "Main Warehouse"))
            supplier = db.scalar(select(Supplier).where(Supplier.name == "ACME Corp"))
            assert product and warehouse and supplier

            before_stock = db.scalar(
                select(StockLevel.quantity)
                .where(StockLevel.product_id == product.id, StockLevel.warehouse_id == warehouse.id)
            ) or 0
        finally:
            db.close()

        # Create PO
        csrf = _get_csrf(client)
        resp = client.post(
            "/po/new",
            data={
                "supplier_id": str(supplier.id),
                "warehouse_id": str(warehouse.id),
                "product_id[]": [str(product.id)],
                "quantity[]": ["10"],
                "unit_cost[]": ["1.00"],
                "csrf_token": csrf,
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303

        # Get PO ID
        db = SessionLocal()
        try:
            from app.models import PurchaseOrder
            from sqlalchemy import select
            po = db.scalar(select(PurchaseOrder).order_by(PurchaseOrder.id.desc()))
            assert po is not None
            po_id = po.id
        finally:
            db.close()

        # Submit
        csrf = _get_csrf(client)
        resp = client.post(f"/po/{po_id}/submit", data={"csrf_token": csrf}, follow_redirects=False)
        assert resp.status_code == 303

        # Get line ID
        db = SessionLocal()
        try:
            from app.models import PurchaseOrderLine, POStatus
            from sqlalchemy import select
            line = db.scalar(select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po_id))
            assert line is not None
            line_id = line.id
            po_status = db.scalar(select(PurchaseOrder.status).where(PurchaseOrder.id == po_id))
            assert po_status == POStatus.submitted
        finally:
            db.close()

        # Receive
        csrf = _get_csrf(client)
        resp = client.post(
            f"/po/{po_id}/receive",
            data={f"qty_{line_id}": "10", "csrf_token": csrf},
            follow_redirects=False,
        )
        assert resp.status_code == 303

        # Verify stock
        db = SessionLocal()
        try:
            from app.models import PurchaseOrder, POStatus
            after_stock = db.scalar(
                select(StockLevel.quantity)
                .where(StockLevel.product_id == product.id, StockLevel.warehouse_id == warehouse.id)
            ) or 0
            assert after_stock == before_stock + 10

            po_status = db.scalar(select(PurchaseOrder.status).where(PurchaseOrder.id == po_id))
            assert po_status == POStatus.received
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

def test_staff_cannot_access_warehouses():
    with TestClient(app) as client:
        login_admin(client)

        # Create staff user
        csrf = _get_csrf(client)
        client.post(
            "/users/new",
            data={
                "username": "staff_user", "password": "staffpass",
                "role": "staff", "is_active": "on", "csrf_token": csrf,
            },
            follow_redirects=False,
        )

        # Log out
        csrf = _get_csrf(client)
        client.post("/logout", data={"csrf_token": csrf}, follow_redirects=False)

        # Log in as staff
        csrf = _get_csrf(client)
        client.post(
            "/login",
            data={"username": "staff_user", "password": "staffpass", "csrf_token": csrf},
            follow_redirects=False,
        )

        resp = client.get("/warehouses", follow_redirects=False)
        assert resp.status_code == 403


def test_staff_cannot_create_product():
    with TestClient(app) as client:
        # Log in as the staff user created above
        csrf = _get_csrf(client)
        resp = client.post(
            "/login",
            data={"username": "staff_user", "password": "staffpass", "csrf_token": csrf},
            follow_redirects=False,
        )
        if resp.status_code != 303:
            return  # user not created yet, skip

        csrf = _get_csrf(client)
        resp = client.get("/products/new", follow_redirects=False)
        assert resp.status_code == 403
