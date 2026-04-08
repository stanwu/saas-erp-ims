from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import get_current_user, tmpl_ctx
from app.models import InventoryMovement, POStatus, Product, PurchaseOrder, StockLevel, User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def root():
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/dashboard")
def dashboard(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Low stock: StockLevel.quantity < Product.reorder_point
    low_stock = db.execute(
        select(Product, StockLevel)
        .join(StockLevel, StockLevel.product_id == Product.id)
        .where(
            Product.is_active == True,  # noqa: E712
            StockLevel.quantity < Product.reorder_point,
            Product.reorder_point > 0,
        )
        .order_by(StockLevel.quantity.asc())
        .limit(20)
    ).all()

    open_po_count = db.scalar(
        select(func.count(PurchaseOrder.id)).where(
            PurchaseOrder.status.in_([POStatus.draft, POStatus.submitted, POStatus.partial])
        )
    ) or 0

    recent_movements = db.scalars(
        select(InventoryMovement)
        .options(
            joinedload(InventoryMovement.product),
            joinedload(InventoryMovement.warehouse),
            joinedload(InventoryMovement.user),
        )
        .order_by(InventoryMovement.created_at.desc())
        .limit(10)
    ).all()

    product_count = db.scalar(select(func.count(Product.id)).where(Product.is_active == True)) or 0  # noqa: E712
    total_movements = db.scalar(select(func.count(InventoryMovement.id))) or 0

    return templates.TemplateResponse(
        request,
        "dashboard/index.html",
        tmpl_ctx(
            request,
            current_user,
            low_stock=low_stock,
            open_po_count=open_po_count,
            recent_movements=recent_movements,
            product_count=product_count,
            total_movements=total_movements,
        ),
    )
