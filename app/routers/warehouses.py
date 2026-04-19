import math

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import flash, require_admin, tmpl_ctx, validate_csrf
from app.models import User, Warehouse

router = APIRouter(prefix="/warehouses", tags=["warehouses"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


@router.get("")
def list_warehouses(
    request: Request,
    page: int = 1,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    per_page = settings.page_size
    total = db.scalar(select(func.count(Warehouse.id))) or 0
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    warehouses = db.scalars(
        select(Warehouse).order_by(Warehouse.name)
        .offset((page - 1) * per_page).limit(per_page)
    ).all()
    return templates.TemplateResponse(
        request,
        "warehouses/list.html",
        tmpl_ctx(request, current_user, warehouses=warehouses, page=page, total_pages=total_pages, total=total),
    )


@router.get("/new")
def new_warehouse_page(
    request: Request,
    current_user: User = Depends(require_admin),
):
    return templates.TemplateResponse(
        request,
        "warehouses/form.html",
        tmpl_ctx(request, current_user, warehouse=None, error=None),
    )


@router.post("/new")
async def create_warehouse(
    request: Request,
    name: str = Form(...),
    location: str = Form(""),
    is_active: str = Form("on"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    warehouse = Warehouse(
        name=name.strip(),
        location=location.strip() or None,
        is_active=bool(is_active),
    )
    db.add(warehouse)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "warehouses/form.html",
            tmpl_ctx(request, current_user, warehouse=None, error="此倉庫名稱已存在。"),
            status_code=400,
        )
    flash(request, f"倉庫「{name}」已建立。", "success")
    return RedirectResponse(url="/warehouses", status_code=303)


@router.get("/{warehouse_id}/edit")
def edit_warehouse_page(
    warehouse_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    warehouse = db.get(Warehouse, warehouse_id)
    if not warehouse:
        return RedirectResponse(url="/warehouses", status_code=303)
    return templates.TemplateResponse(
        request,
        "warehouses/form.html",
        tmpl_ctx(request, current_user, warehouse=warehouse, error=None),
    )


@router.post("/{warehouse_id}/edit")
async def edit_warehouse(
    warehouse_id: int,
    request: Request,
    name: str = Form(...),
    location: str = Form(""),
    is_active: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    warehouse = db.get(Warehouse, warehouse_id)
    if not warehouse:
        return RedirectResponse(url="/warehouses", status_code=303)
    warehouse.name = name.strip()
    warehouse.location = location.strip() or None
    warehouse.is_active = bool(is_active)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "warehouses/form.html",
            tmpl_ctx(request, current_user, warehouse=warehouse, error="此倉庫名稱已存在。"),
            status_code=400,
        )
    flash(request, f"倉庫「{warehouse.name}」已更新。", "success")
    return RedirectResponse(url="/warehouses", status_code=303)
