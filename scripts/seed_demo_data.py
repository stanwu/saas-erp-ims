"""Seed the local database with default demo data."""

from app.bootstrap import init_db, seed_initial_data
from app.database import SessionLocal
from app.demo_seed import seed_demo_data
from app.models import (
    InventoryMovement,
    Product,
    PurchaseOrder,
    StockLevel,
    Supplier,
    User,
    Warehouse,
)


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        seed_initial_data(db)
        seed_demo_data(db, cleanup_legacy=True)
        counts = {
            "users": db.query(User).count(),
            "warehouses": db.query(Warehouse).count(),
            "suppliers": db.query(Supplier).count(),
            "products": db.query(Product).count(),
            "movements": db.query(InventoryMovement).count(),
            "purchase_orders": db.query(PurchaseOrder).count(),
            "stock_levels": db.query(StockLevel).count(),
        }
        print("Demo data ready:")
        for key, value in counts.items():
            print(f"  {key}: {value}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
