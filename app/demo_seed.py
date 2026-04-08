from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Category,
    InventoryMovement,
    MovementType,
    OUTBOUND_TYPES,
    POStatus,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    StockLevel,
    Supplier,
    User,
    UserRole,
    Warehouse,
)
from app.security import hash_password
from app.services import record_movement


WAREHOUSES = [
    ("Taipei Main Warehouse", "Neihu District, Taipei"),
    ("Taoyuan Backup Warehouse", "Guishan District, Taoyuan"),
    ("Taichung Parts Warehouse", "Xitun District, Taichung"),
]

SUPPLIERS = [
    {"name": "WT Microelectronics", "contact_person": "David Wang", "email": "wtmec.procurement@example.com", "phone": "02-1234-5678"},  # sensitive-data: allow
    {"name": "Yageo Corporation", "contact_person": "Ivy Lin", "email": "yageo.sourcing@example.com", "phone": "03-5678-9000"},  # sensitive-data: allow
    {"name": "Delta Electronics", "contact_person": "Kevin Liu", "email": "delta.ops@example.com", "phone": "+886-4-2452-7788"},  # sensitive-data: allow
    {"name": "Lite-On Technology", "contact_person": "Mia Chen", "email": "liteon.procurement@example.com", "phone": "+886-2-2658-0001"},  # sensitive-data: allow
    {"name": "ASE Technology Holding", "contact_person": "Ryan Hsu", "email": "ase.supply@example.com", "phone": "+886-7-361-7131"},  # sensitive-data: allow
    {"name": "WPG Holdings", "contact_person": "Sharon Wu", "email": "wpg.vendor@example.com", "phone": "+886-2-3327-7777"},  # sensitive-data: allow
    {"name": "Advantech", "contact_person": "Oliver Tsai", "email": "advantech.procurement@example.com", "phone": "+886-2-8751-6699"},  # sensitive-data: allow
    {"name": "Quanta Computer", "contact_person": "Jason Kuo", "email": "quanta.scm@example.com", "phone": "+886-3-327-2345"},  # sensitive-data: allow
    {"name": "Chicony Power Technology", "contact_person": "Emily Huang", "email": "chicony.power@example.com", "phone": "+886-2-2708-7698"},  # sensitive-data: allow
    {"name": "Foxconn Interconnect Technology", "contact_person": "Allen Chang", "email": "fit.supply@example.com", "phone": "+886-3-578-2258"},  # sensitive-data: allow
    {"name": "Wistron", "contact_person": "Grace Yeh", "email": "wistron.vendor@example.com", "phone": "+886-2-2182-1313"},  # sensitive-data: allow
    {"name": "Pegatron", "contact_person": "Victor Peng", "email": "pegatron.enterprise@example.com", "phone": "+886-2-2344-5678"},  # sensitive-data: allow
]

USERS = [
    ("warehouse.ops", "demo12345", UserRole.staff),
    ("purchasing.lead", "demo12345", UserRole.admin),
    ("auditor.team", "demo12345", UserRole.staff),
    ("sales.coordinator", "demo12345", UserRole.staff),
]

PRODUCTS = [
    ("MCU-001", "STM32F103 Microcontroller", "25.50", 30, "Core controller used in main boards and sensor modules"),
    ("RES-100", "100 Ohm Resistor 1/4W", "0.35", 200, "Standard passive component for general assembly"),
    ("CAP-010", "10uF 25V Capacitor", "0.80", 120, "Used for power filtering and decoupling"),
    ("LED-RED", "Red LED 5mm", "1.20", 80, "Indicator light component for equipment panels"),
    ("PCB-001", "Main Control Board Rev 2.0", "120.00", 15, "Second production revision of the main board"),
    ("SEN-TMP", "Temperature Sensor Module", "48.00", 25, "Module for environment monitoring and alerts"),
    ("PWR-24V", "24V Power Supply Module", "210.00", 12, "Power module for industrial control equipment"),
    ("CASE-ALU", "Aluminum Enclosure", "95.00", 18, "Protective housing for the assembled device"),
    ("RELAY-12V", "12V Signal Relay", "18.50", 40, "Relay used for switching and control logic circuits"),
    ("FUSE-5A", "5A Mini Blade Fuse", "3.20", 60, "Replaceable protection fuse for field service"),
    ("CABLE-01", "Shielded Signal Cable", "14.00", 25, "Pre-cut cable assembly for panel wiring"),
    ("SEN-PIR", "PIR Motion Sensor", "32.00", 20, "Motion sensing module for security and automation"),
]

MOVEMENTS = [
    ("MCU-001", "Taipei Main Warehouse", MovementType.in_, 150, "Initial stock for Taipei main warehouse"),
    ("RES-100", "Taipei Main Warehouse", MovementType.in_, 600, "First passive components shipment received"),
    ("CAP-010", "Taipei Main Warehouse", MovementType.in_, 320, "Capacitor stock initialized"),
    ("LED-RED", "Taipei Main Warehouse", MovementType.in_, 180, "LED components received into stock"),
    ("PCB-001", "Taipei Main Warehouse", MovementType.in_, 28, "First production batch completed"),
    ("SEN-TMP", "Taoyuan Backup Warehouse", MovementType.in_, 55, "Backup stock prepared in Taoyuan"),
    ("PWR-24V", "Taoyuan Backup Warehouse", MovementType.in_, 20, "24V power modules received"),
    ("CASE-ALU", "Taichung Parts Warehouse", MovementType.in_, 24, "Safety stock stored in Taichung"),
    ("MCU-001", "Taipei Main Warehouse", MovementType.out, 45, "Engineering prototype build allocation"),
    ("RES-100", "Taipei Main Warehouse", MovementType.out, 180, "Production work order material issue"),
    ("PCB-001", "Taipei Main Warehouse", MovementType.out, 6, "Finished goods moved to assembly"),
    ("SEN-TMP", "Taoyuan Backup Warehouse", MovementType.adjust_add, 4, "Cycle count positive adjustment"),
    ("PWR-24V", "Taoyuan Backup Warehouse", MovementType.adjust_sub, 2, "Scrap deduction after inspection"),
    ("CASE-ALU", "Taichung Parts Warehouse", MovementType.transfer_out, 5, "Transferred to Taipei main warehouse"),
    ("CASE-ALU", "Taipei Main Warehouse", MovementType.transfer_in, 5, "Received from Taichung parts warehouse"),
    ("RELAY-12V", "Taipei Main Warehouse", MovementType.in_, 34, "Relay stock initialized"),
    ("FUSE-5A", "Taipei Main Warehouse", MovementType.in_, 120, "Service fuse inventory received"),
    ("CABLE-01", "Taoyuan Backup Warehouse", MovementType.in_, 18, "Backup cable stock prepared"),
    ("SEN-PIR", "Taichung Parts Warehouse", MovementType.in_, 12, "Motion sensor stock received"),
    ("RELAY-12V", "Taipei Main Warehouse", MovementType.out, 9, "Panel assembly allocation"),
    ("FUSE-5A", "Taipei Main Warehouse", MovementType.out, 25, "Service kit replenishment"),
    ("CABLE-01", "Taoyuan Backup Warehouse", MovementType.adjust_add, 3, "Receiving count correction"),
    ("SEN-PIR", "Taichung Parts Warehouse", MovementType.out, 3, "Demo kit preparation"),
]

PURCHASE_ORDERS = [
    {
        "po_number": "DEMO-PO-001",
        "supplier": "WT Microelectronics",
        "warehouse": "Taipei Main Warehouse",
        "status": POStatus.partial,
        "expected_at": datetime(2026, 4, 15),
        "received_at": None,
        "lines": [
            ("MCU-001", 120, 60, "22.00"),
            ("SEN-TMP", 24, 12, "44.00"),
            ("RELAY-12V", 60, 20, "15.80"),
            ("PWR-24V", 10, 5, "195.00"),
        ],
    },
    {
        "po_number": "DEMO-PO-002",
        "supplier": "Yageo Corporation",
        "warehouse": "Taoyuan Backup Warehouse",
        "status": POStatus.submitted,
        "expected_at": datetime(2026, 4, 18),
        "received_at": None,
        "lines": [
            ("RES-100", 1000, 0, "0.28"),
            ("CAP-010", 600, 0, "0.72"),
            ("FUSE-5A", 300, 0, "2.60"),
        ],
    },
    {
        "po_number": "DEMO-PO-003",
        "supplier": "Foxconn Interconnect Technology",
        "warehouse": "Taichung Parts Warehouse",
        "status": POStatus.draft,
        "expected_at": datetime(2026, 4, 22),
        "received_at": None,
        "lines": [
            ("CASE-ALU", 40, 0, "88.00"),
            ("CABLE-01", 60, 0, "12.80"),
        ],
    },
    {
        "po_number": "DEMO-PO-004",
        "supplier": "Lite-On Technology",
        "warehouse": "Taipei Main Warehouse",
        "status": POStatus.received,
        "expected_at": datetime(2026, 4, 10),
        "received_at": datetime(2026, 4, 10, 16, 30),
        "lines": [
            ("LED-RED", 240, 240, "0.95"),
            ("RELAY-12V", 40, 40, "16.50"),
        ],
    },
]

LEGACY_SUPPLIER_NAMES = {
    "Taiwan Electronic Components Co.",
    "South China Industrial Materials Ltd.",
    "Global Components Trading",
}


def should_seed_demo_data(db: Session) -> bool:
    return (
        (db.scalar(select(func.count(User.id))) or 0) <= 1
        and (db.scalar(select(func.count(Product.id))) or 0) == 0
        and (db.scalar(select(func.count(Supplier.id))) or 0) == 0
        and (db.scalar(select(func.count(PurchaseOrder.id))) or 0) == 0
    )


def get_one_by_name(db: Session, model, field_name: str, value: str):
    return db.scalar(select(model).where(getattr(model, field_name) == value))


def cleanup_legacy_demo_data(db: Session) -> None:
    legacy_pos = db.scalars(
        select(PurchaseOrder)
        .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
        .where(Supplier.name.in_(LEGACY_SUPPLIER_NAMES))
    ).all()
    legacy_po_ids = [po.id for po in legacy_pos]
    if legacy_po_ids:
        for movement in db.scalars(
            select(InventoryMovement).where(
                InventoryMovement.reference_type == "purchase_order",
                InventoryMovement.reference_id.in_(legacy_po_ids),
            )
        ).all():
            db.delete(movement)
        for po in legacy_pos:
            db.delete(po)

    for supplier in db.scalars(select(Supplier).where(Supplier.name.in_(LEGACY_SUPPLIER_NAMES))).all():
        still_used = db.scalar(select(PurchaseOrder.id).where(PurchaseOrder.supplier_id == supplier.id).limit(1))
        if still_used is None:
            db.delete(supplier)


def ensure_users(db: Session) -> None:
    for username, password, role in USERS:
        user = db.scalar(select(User).where(User.username == username))
        if user:
            user.role = role
            user.is_active = True
            continue
        db.add(User(username=username, password_hash=hash_password(password), role=role, is_active=True))


def ensure_warehouses(db: Session) -> None:
    for name, location in WAREHOUSES:
        warehouse = db.scalar(select(Warehouse).where(Warehouse.name == name))
        if warehouse:
            warehouse.location = location
            warehouse.is_active = True
            continue
        db.add(Warehouse(name=name, location=location, is_active=True))


def ensure_suppliers(db: Session) -> None:
    for payload in SUPPLIERS:
        supplier = db.scalar(select(Supplier).where(Supplier.name == payload["name"]))
        if supplier:
            supplier.contact_person = payload["contact_person"]
            supplier.email = payload["email"]
            supplier.phone = payload["phone"]
            supplier.is_active = True
            continue
        db.add(Supplier(**payload, is_active=True))


def ensure_products(db: Session) -> None:
    general = db.scalar(select(Category).where(Category.name == "General"))
    if general is None:
        general = Category(name="General", description="General category")
        db.add(general)
        db.flush()

    for sku, name, cost_price, reorder_point, description in PRODUCTS:
        product = db.scalar(select(Product).where(Product.sku == sku))
        if product:
            product.name = name
            product.cost_price = cost_price
            product.reorder_point = reorder_point
            product.description = description
            product.unit = "pcs"
            product.category_id = general.id
            product.is_active = True
            continue
        db.add(
            Product(
                sku=sku,
                name=name,
                unit="pcs",
                cost_price=cost_price,
                reorder_point=reorder_point,
                description=description,
                category_id=general.id,
                is_active=True,
            )
        )


def ensure_movement(db: Session, admin_id: int, sku: str, warehouse_name: str, movement_type: MovementType, quantity: int, note: str) -> None:
    if db.scalar(select(InventoryMovement).where(InventoryMovement.note == note)):
        return

    product = get_one_by_name(db, Product, "sku", sku)
    warehouse = get_one_by_name(db, Warehouse, "name", warehouse_name)
    if not product or not warehouse:
        raise RuntimeError(f"Missing product or warehouse for movement: {sku} / {warehouse_name}")

    stock = db.scalar(select(StockLevel).where(StockLevel.product_id == product.id, StockLevel.warehouse_id == warehouse.id))
    current_qty = stock.quantity if stock else 0
    if movement_type in OUTBOUND_TYPES and current_qty < quantity:
        top_up_qty = quantity - current_qty
        baseline_note = f"Demo baseline stock for {sku} at {warehouse_name}"
        if not db.scalar(select(InventoryMovement).where(InventoryMovement.note == baseline_note)):
            record_movement(
                db,
                product_id=product.id,
                warehouse_id=warehouse.id,
                movement_type=MovementType.in_,
                quantity=top_up_qty,
                user_id=admin_id,
                note=baseline_note,
            )

    record_movement(
        db,
        product_id=product.id,
        warehouse_id=warehouse.id,
        movement_type=movement_type,
        quantity=quantity,
        user_id=admin_id,
        note=note,
    )


def ensure_purchase_order(db: Session, admin_id: int, payload: dict) -> None:
    if db.scalar(select(PurchaseOrder).where(PurchaseOrder.po_number == payload["po_number"])):
        return

    supplier = get_one_by_name(db, Supplier, "name", payload["supplier"])
    warehouse = get_one_by_name(db, Warehouse, "name", payload["warehouse"])
    if not supplier or not warehouse:
        raise RuntimeError(f"Missing supplier or warehouse for {payload['po_number']}")

    po = PurchaseOrder(
        po_number=payload["po_number"],
        supplier_id=supplier.id,
        warehouse_id=warehouse.id,
        status=payload["status"],
        expected_at=payload["expected_at"],
        received_at=payload["received_at"],
        created_by=admin_id,
    )
    db.add(po)
    db.flush()

    for sku, qty_ordered, qty_received, unit_cost in payload["lines"]:
        product = get_one_by_name(db, Product, "sku", sku)
        if not product:
            raise RuntimeError(f"Missing product for PO line: {sku}")
        db.add(
            PurchaseOrderLine(
                po_id=po.id,
                product_id=product.id,
                quantity_ordered=qty_ordered,
                quantity_received=qty_received,
                unit_cost=unit_cost,
            )
        )
        if qty_received > 0:
            existing = db.scalar(
                select(InventoryMovement).where(
                    InventoryMovement.reference_type == "purchase_order",
                    InventoryMovement.reference_id == po.id,
                    InventoryMovement.product_id == product.id,
                )
            )
            if not existing:
                record_movement(
                    db,
                    product_id=product.id,
                    warehouse_id=warehouse.id,
                    movement_type=MovementType.in_,
                    quantity=qty_received,
                    user_id=admin_id,
                    reference_type="purchase_order",
                    reference_id=po.id,
                    note=f"Received from PO {po.po_number}",
                )


def seed_demo_data(db: Session, *, cleanup_legacy: bool = False) -> None:
    if cleanup_legacy:
        cleanup_legacy_demo_data(db)

    ensure_warehouses(db)
    ensure_suppliers(db)
    ensure_users(db)
    ensure_products(db)
    db.commit()

    admin = db.scalar(select(User).where(User.username == "admin"))
    if admin is None:
        raise RuntimeError("Admin user not found")

    for sku, warehouse_name, movement_type, quantity, note in MOVEMENTS:
        ensure_movement(db, admin.id, sku, warehouse_name, movement_type, quantity, note)
    db.commit()

    for payload in PURCHASE_ORDERS:
        ensure_purchase_order(db, admin.id, payload)
    db.commit()
