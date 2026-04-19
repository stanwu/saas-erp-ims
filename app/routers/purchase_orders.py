import math
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.dependencies import flash, get_current_user, require_admin, tmpl_ctx, validate_csrf
from app.models import (
    POStatus, PO_STATUS_BADGE, Product, PurchaseOrder, PurchaseOrderLine,
    Supplier, User, Warehouse, MovementType,
)
from app.services import generate_po_number, record_movement

router = APIRouter(prefix="/po", tags=["purchase_orders"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


def _load_po(db: Session, po_id: int) -> PurchaseOrder | None:
    return db.scalar(
        select(PurchaseOrder)
        .options(
            joinedload(PurchaseOrder.supplier),
            joinedload(PurchaseOrder.warehouse),
            joinedload(PurchaseOrder.created_by_user),
            joinedload(PurchaseOrder.lines).joinedload(PurchaseOrderLine.product),
        )
        .where(PurchaseOrder.id == po_id)
    )


@router.get("")
def list_pos(
    request: Request,
    page: int = 1,
    status: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    per_page = settings.page_size
    stmt = select(PurchaseOrder).options(
        joinedload(PurchaseOrder.supplier),
        joinedload(PurchaseOrder.warehouse),
    )
    if status:
        stmt = stmt.where(PurchaseOrder.status == POStatus(status))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    pos = db.scalars(
        stmt.order_by(PurchaseOrder.created_at.desc())
        .offset((page - 1) * per_page).limit(per_page)
    ).all()

    extra_params = f"&status={status}" if status else ""
    return templates.TemplateResponse(
        request,
        "purchase_orders/list.html",
        tmpl_ctx(request, current_user,
                 pos=pos, statuses=list(POStatus), selected_status=status,
                 status_badge=PO_STATUS_BADGE,
                 page=page, total_pages=total_pages, total=total,
                 extra_params=extra_params),
    )


@router.get("/new")
def new_po_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    suppliers = db.scalars(select(Supplier).where(Supplier.is_active == True).order_by(Supplier.name)).all()  # noqa: E712
    warehouses = db.scalars(select(Warehouse).where(Warehouse.is_active == True).order_by(Warehouse.name)).all()  # noqa: E712
    products = db.scalars(select(Product).where(Product.is_active == True).order_by(Product.name)).all()  # noqa: E712
    return templates.TemplateResponse(
        request,
        "purchase_orders/form.html",
        tmpl_ctx(request, current_user,
                 suppliers=suppliers, warehouses=warehouses, products=products, error=None),
    )


@router.post("/new")
async def create_po(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    form = await request.form()
    supplier_id = int(form.get("supplier_id", 0))
    warehouse_id = int(form.get("warehouse_id", 0))
    expected_at_str = form.get("expected_at", "")

    product_ids = form.getlist("product_id[]")
    quantities = form.getlist("quantity[]")
    unit_costs = form.getlist("unit_cost[]")

    suppliers = db.scalars(select(Supplier).where(Supplier.is_active == True).order_by(Supplier.name)).all()  # noqa: E712
    warehouses = db.scalars(select(Warehouse).where(Warehouse.is_active == True).order_by(Warehouse.name)).all()  # noqa: E712
    products = db.scalars(select(Product).where(Product.is_active == True).order_by(Product.name)).all()  # noqa: E712

    if not product_ids:
        return templates.TemplateResponse(
            request, "purchase_orders/form.html",
            tmpl_ctx(request, current_user,
                     suppliers=suppliers, warehouses=warehouses, products=products,
                     error="至少需要一個明細項目。"),
            status_code=400,
        )

    po = PurchaseOrder(
        po_number=generate_po_number(db),
        supplier_id=supplier_id,
        warehouse_id=warehouse_id,
        status=POStatus.draft,
        created_by=current_user.id,
        expected_at=datetime.fromisoformat(expected_at_str) if expected_at_str else None,
    )
    db.add(po)
    db.flush()

    for pid, qty, uc in zip(product_ids, quantities, unit_costs):
        if not pid or not qty:
            continue
        line = PurchaseOrderLine(
            po_id=po.id,
            product_id=int(pid),
            quantity_ordered=int(qty),
            unit_cost=float(uc) if uc else 0,
        )
        db.add(line)

    db.commit()
    flash(request, f"採購單 {po.po_number} 已建立。", "success")
    return RedirectResponse(url=f"/po/{po.id}", status_code=303)


@router.get("/{po_id}")
def po_detail(
    po_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    po = _load_po(db, po_id)
    if not po:
        return RedirectResponse(url="/po", status_code=303)
    return templates.TemplateResponse(
        request,
        "purchase_orders/detail.html",
        tmpl_ctx(request, current_user, po=po, status_badge=PO_STATUS_BADGE),
    )


@router.post("/{po_id}/submit")
async def submit_po(
    po_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    po = db.get(PurchaseOrder, po_id)
    if po and po.status == POStatus.draft:
        po.status = POStatus.submitted
        db.commit()
        flash(request, f"採購單 {po.po_number} 已提交。", "success")
    return RedirectResponse(url=f"/po/{po_id}", status_code=303)


@router.get("/{po_id}/receive")
def receive_po_page(
    po_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    po = _load_po(db, po_id)
    if not po or po.status not in (POStatus.submitted, POStatus.partial):
        return RedirectResponse(url=f"/po/{po_id}", status_code=303)
    return templates.TemplateResponse(
        request,
        "purchase_orders/receive.html",
        tmpl_ctx(request, current_user, po=po, status_badge=PO_STATUS_BADGE),
    )


@router.post("/{po_id}/receive")
async def receive_po(
    po_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    po = _load_po(db, po_id)
    if not po or po.status not in (POStatus.submitted, POStatus.partial):
        return RedirectResponse(url=f"/po/{po_id}", status_code=303)

    form = await request.form()
    errors = []

    for line in po.lines:
        raw = form.get(f"qty_{line.id}", "0")
        try:
            qty = int(raw)
        except ValueError:
            qty = 0
        if qty <= 0:
            continue
        remaining = line.quantity_ordered - line.quantity_received
        if qty > remaining:
            errors.append(f"{line.product.name}：無法收貨 {qty}，剩餘 {remaining}")
            continue
        try:
            record_movement(
                db,
                product_id=line.product_id,
                warehouse_id=po.warehouse_id,
                movement_type=MovementType.in_,
                quantity=qty,
                user_id=current_user.id,
                reference_type="purchase_order",
                reference_id=po.id,
                note=f"Received from PO {po.po_number}",
            )
            line.quantity_received += qty
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        db.rollback()
        po = _load_po(db, po_id)
        return templates.TemplateResponse(
            request,
            "purchase_orders/receive.html",
            tmpl_ctx(request, current_user, po=po, status_badge=PO_STATUS_BADGE,
                     errors=errors),
            status_code=400,
        )

    # Update PO status
    all_received = all(l.quantity_received >= l.quantity_ordered for l in po.lines)
    po.status = POStatus.received if all_received else POStatus.partial
    if all_received:
        po.received_at = datetime.now()

    db.commit()
    flash(request, f"採購單 {po.po_number} 已收貨。", "success")
    return RedirectResponse(url=f"/po/{po_id}", status_code=303)


@router.post("/{po_id}/cancel")
async def cancel_po(
    po_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    po = db.get(PurchaseOrder, po_id)
    if po and po.status in (POStatus.draft, POStatus.submitted):
        po.status = POStatus.cancelled
        db.commit()
        flash(request, f"採購單 {po.po_number} 已取消。", "warning")
    return RedirectResponse(url=f"/po/{po_id}", status_code=303)
