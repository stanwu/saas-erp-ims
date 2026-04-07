from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import InventoryMovement, Product, User
from app.templates import templates


router = APIRouter()


@router.get("/")
def root():
    return {"message": "ERP IMS is running."}


@router.get("/dashboard")
def dashboard(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product_count = db.scalar(select(func.count(Product.id))) or 0
    active_product_count = db.scalar(select(func.count(Product.id)).where(Product.is_active.is_(True))) or 0
    movement_count = db.scalar(select(func.count(InventoryMovement.id))) or 0
    total_stock = db.scalar(select(func.coalesce(func.sum(Product.stock_quantity), 0))) or 0
    recent_movements = db.scalars(
        select(InventoryMovement).order_by(InventoryMovement.created_at.desc()).limit(10)
    ).all()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "current_user": current_user,
            "product_count": product_count,
            "active_product_count": active_product_count,
            "movement_count": movement_count,
            "total_stock": total_stock,
            "recent_movements": recent_movements,
        },
    )
