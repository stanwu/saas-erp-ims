from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InventoryMovement, MovementType, Product, User


def authenticate_user(db: Session, username_or_email: str, verify_password_func, password: str) -> User | None:
    stmt = select(User).where(
        (User.username == username_or_email) | (User.email == username_or_email)
    )
    user = db.scalar(stmt)
    if not user or not user.is_active:
        return None
    if not verify_password_func(password, user.password_hash):
        return None
    return user


def apply_inventory_movement(
    db: Session,
    *,
    product: Product,
    actor: User,
    movement_type: MovementType,
    quantity: int,
    note: str,
) -> InventoryMovement:
    if not product.is_active:
        raise ValueError("Inactive products cannot accept inventory movements.")

    if movement_type == MovementType.IN:
        if quantity <= 0:
            raise ValueError("Quantity must be greater than 0.")
        delta = quantity
    elif movement_type == MovementType.OUT:
        if quantity <= 0:
            raise ValueError("Quantity must be greater than 0.")
        delta = -quantity
    else:
        if quantity == 0:
            raise ValueError("Adjustment quantity cannot be 0.")
        delta = quantity

    new_quantity = product.stock_quantity + delta
    if new_quantity < 0:
        raise ValueError("Insufficient stock for this movement.")

    product.stock_quantity = new_quantity
    movement = InventoryMovement(
        product=product,
        user=actor,
        movement_type=movement_type,
        quantity=abs(quantity),
        delta=delta,
        note=note.strip(),
    )
    db.add(movement)
    db.add(product)
    db.commit()
    db.refresh(movement)
    return movement
