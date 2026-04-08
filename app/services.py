from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    InventoryMovement, MovementType, OUTBOUND_TYPES,
    PurchaseOrder, StockLevel, User,
)
from app.security import verify_password


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.username == username, User.is_active == True))  # noqa: E712
    if user and verify_password(password, user.password_hash):
        return user
    return None


def generate_po_number(db: Session) -> str:
    year = datetime.now().year
    count = db.query(PurchaseOrder).filter(
        PurchaseOrder.po_number.like(f"PO-{year}-%")
    ).count()
    return f"PO-{year}-{count + 1:05d}"


def record_movement(
    db: Session,
    product_id: int,
    warehouse_id: int,
    movement_type: MovementType,
    quantity: int,
    user_id: int,
    reference_type: str | None = None,
    reference_id: int | None = None,
    note: str = "",
) -> InventoryMovement:
    if quantity <= 0:
        raise ValueError("Quantity must be positive")

    # Acquire row-level lock (creates row if missing)
    stock = db.scalar(
        select(StockLevel)
        .where(StockLevel.product_id == product_id, StockLevel.warehouse_id == warehouse_id)
        .with_for_update()
    )
    if stock is None:
        stock = StockLevel(product_id=product_id, warehouse_id=warehouse_id, quantity=0)
        db.add(stock)
        db.flush()

    if movement_type in OUTBOUND_TYPES:
        if stock.quantity < quantity:
            raise ValueError(
                f"Insufficient stock: available {stock.quantity}, requested {quantity}"
            )
        stock.quantity -= quantity
    else:
        stock.quantity += quantity

    movement = InventoryMovement(
        product_id=product_id,
        warehouse_id=warehouse_id,
        user_id=user_id,
        movement_type=movement_type,
        quantity=quantity,
        reference_type=reference_type,
        reference_id=reference_id,
        note=note,
    )
    db.add(movement)
    return movement
