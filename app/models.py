import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer,
    Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    staff = "staff"


class MovementType(str, enum.Enum):
    in_ = "in"
    out = "out"
    adjust_add = "adjust_add"
    adjust_sub = "adjust_sub"
    transfer_in = "transfer_in"
    transfer_out = "transfer_out"


MOVEMENT_LABELS = {
    MovementType.in_: "入庫",
    MovementType.out: "出庫",
    MovementType.adjust_add: "盤點調增",
    MovementType.adjust_sub: "盤點調減",
    MovementType.transfer_in: "轉入",
    MovementType.transfer_out: "轉出",
}

OUTBOUND_TYPES = {MovementType.out, MovementType.adjust_sub, MovementType.transfer_out}


class POStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    partial = "partial"
    received = "received"
    cancelled = "cancelled"


PO_STATUS_BADGE = {
    POStatus.draft: "secondary",
    POStatus.submitted: "primary",
    POStatus.partial: "warning",
    POStatus.received: "success",
    POStatus.cancelled: "danger",
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.staff, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    movements: Mapped[list["InventoryMovement"]] = relationship(back_populates="user")
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="created_by_user")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    stock_levels: Mapped[list["StockLevel"]] = relationship(back_populates="warehouse")
    movements: Mapped[list["InventoryMovement"]] = relationship(back_populates="warehouse")
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="warehouse")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    unit: Mapped[str] = mapped_column(String(16), default="pcs", nullable=False)
    cost_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    reorder_point: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    category: Mapped["Category | None"] = relationship(back_populates="products")
    stock_levels: Mapped[list["StockLevel"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    movements: Mapped[list["InventoryMovement"]] = relationship(back_populates="product")
    po_lines: Mapped[list["PurchaseOrderLine"]] = relationship(back_populates="product")


class StockLevel(Base):
    __tablename__ = "stock_levels"
    __table_args__ = (UniqueConstraint("product_id", "warehouse_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    product: Mapped["Product"] = relationship(back_populates="stock_levels")
    warehouse: Mapped["Warehouse"] = relationship(back_populates="stock_levels")


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    movement_type: Mapped[MovementType] = mapped_column(Enum(MovementType), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reference_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    product: Mapped["Product"] = relationship(back_populates="movements")
    warehouse: Mapped["Warehouse"] = relationship(back_populates="movements")
    user: Mapped["User"] = relationship(back_populates="movements")


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    contact_person: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="supplier")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    po_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    status: Mapped[POStatus] = mapped_column(Enum(POStatus), default=POStatus.draft, nullable=False)
    ordered_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    expected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    supplier: Mapped["Supplier"] = relationship(back_populates="purchase_orders")
    warehouse: Mapped["Warehouse"] = relationship(back_populates="purchase_orders")
    created_by_user: Mapped["User"] = relationship(back_populates="purchase_orders")
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(back_populates="po", cascade="all, delete-orphan")


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"
    __table_args__ = (UniqueConstraint("po_id", "product_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    po: Mapped["PurchaseOrder"] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship(back_populates="po_lines")
