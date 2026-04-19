import math

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.dependencies import flash, get_current_user, tmpl_ctx, validate_csrf
from app.models import InventoryMovement, MOVEMENT_LABELS, MovementType, Product, User, Warehouse

router = APIRouter(prefix="/movements", tags=["movements"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


@router.get("")
def list_movements(
    request: Request,
    page: int = 1,
    warehouse_id: str = "",
    movement_type: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    per_page = settings.page_size
    stmt = (
        select(InventoryMovement)
        .options(
            joinedload(InventoryMovement.product),
            joinedload(InventoryMovement.warehouse),
            joinedload(InventoryMovement.user),
        )
    )
    if warehouse_id:
        stmt = stmt.where(InventoryMovement.warehouse_id == int(warehouse_id))
    if movement_type:
        stmt = stmt.where(InventoryMovement.movement_type == MovementType(movement_type))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    movements = db.scalars(
        stmt.order_by(InventoryMovement.created_at.desc())
        .offset((page - 1) * per_page).limit(per_page)
    ).all()

    warehouses = db.scalars(select(Warehouse).order_by(Warehouse.name)).all()
    extra_params = ""
    if warehouse_id:
        extra_params += f"&warehouse_id={warehouse_id}"
    if movement_type:
        extra_params += f"&movement_type={movement_type}"

    return templates.TemplateResponse(
        request,
        "movements/list.html",
        tmpl_ctx(request, current_user,
                 movements=movements, warehouses=warehouses,
                 movement_types=list(MovementType), movement_labels=MOVEMENT_LABELS,
                 selected_warehouse=warehouse_id, selected_type=movement_type,
                 page=page, total_pages=total_pages, total=total,
                 extra_params=extra_params),
    )


@router.get("/new")
def new_movement_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    products = db.scalars(select(Product).where(Product.is_active == True).order_by(Product.name)).all()  # noqa: E712
    warehouses = db.scalars(select(Warehouse).where(Warehouse.is_active == True).order_by(Warehouse.name)).all()  # noqa: E712
    return templates.TemplateResponse(
        request,
        "movements/form.html",
        tmpl_ctx(request, current_user,
                 products=products, warehouses=warehouses,
                 movement_types=list(MovementType), movement_labels=MOVEMENT_LABELS,
                 error=None, form={}),
    )


@router.post("/new")
async def create_movement(
    request: Request,
    product_id: int = Form(...),
    warehouse_id: int = Form(...),
    movement_type: str = Form(...),
    quantity: int = Form(...),
    note: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    from app.services import record_movement

    products = db.scalars(select(Product).where(Product.is_active == True).order_by(Product.name)).all()  # noqa: E712
    warehouses = db.scalars(select(Warehouse).where(Warehouse.is_active == True).order_by(Warehouse.name)).all()  # noqa: E712
    form_data = {"product_id": product_id, "warehouse_id": warehouse_id,
                 "movement_type": movement_type, "quantity": quantity, "note": note}

    try:
        mov_type = MovementType(movement_type)
        record_movement(db, product_id, warehouse_id, mov_type, quantity, current_user.id, note=note)
        db.commit()
    except (ValueError, Exception) as exc:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "movements/form.html",
            tmpl_ctx(request, current_user,
                     products=products, warehouses=warehouses,
                     movement_types=list(MovementType), movement_labels=MOVEMENT_LABELS,
                     error=str(exc), form=form_data),
            status_code=400,
        )

    flash(request, "庫存異動已記錄。", "success")
    return RedirectResponse(url="/movements", status_code=303)
