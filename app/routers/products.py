import math

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.dependencies import flash, get_current_user, require_admin, tmpl_ctx, validate_csrf
from app.models import Category, InventoryMovement, Product, StockLevel, User, Warehouse

router = APIRouter(prefix="/products", tags=["products"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


@router.get("")
def list_products(
    request: Request,
    page: int = 1,
    q: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    per_page = settings.page_size
    stmt = select(Product).options(joinedload(Product.category))
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%") | Product.sku.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    products = db.scalars(
        stmt.order_by(Product.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).all()

    # Attach total stock
    stock_totals = dict(
        db.execute(
            select(StockLevel.product_id, func.sum(StockLevel.quantity))
            .group_by(StockLevel.product_id)
        ).all()
    )

    return templates.TemplateResponse(
        request,
        "products/list.html",
        tmpl_ctx(request, current_user, products=products, stock_totals=stock_totals,
                 q=q, page=page, total_pages=total_pages, total=total),
    )


@router.get("/new")
def new_product_page(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    categories = db.scalars(select(Category).order_by(Category.name)).all()
    return templates.TemplateResponse(
        request,
        "products/form.html",
        tmpl_ctx(request, current_user, product=None, categories=categories, error=None),
    )


@router.post("/new")
async def create_product(
    request: Request,
    sku: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    category_id: str = Form(""),
    unit: str = Form("pcs"),
    cost_price: float = Form(0),
    reorder_point: int = Form(0),
    is_active: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    categories = db.scalars(select(Category).order_by(Category.name)).all()
    product = Product(
        sku=sku.strip(),
        name=name.strip(),
        description=description.strip(),
        category_id=int(category_id) if category_id else None,
        unit=unit.strip() or "pcs",
        cost_price=cost_price,
        reorder_point=reorder_point,
        is_active=bool(is_active),
    )
    db.add(product)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "products/form.html",
            tmpl_ctx(request, current_user, product=None, categories=categories, error="此 SKU 已存在。"),
            status_code=400,
        )
    flash(request, f"商品「{name}」已建立。", "success")
    return RedirectResponse(url="/products", status_code=303)


@router.get("/{product_id}")
def product_detail(
    product_id: int,
    request: Request,
    page: int = 1,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = db.scalar(
        select(Product).options(joinedload(Product.category)).where(Product.id == product_id)
    )
    if not product:
        return RedirectResponse(url="/products", status_code=303)

    stock_levels = db.scalars(
        select(StockLevel)
        .options(joinedload(StockLevel.warehouse))
        .where(StockLevel.product_id == product_id)
    ).all()

    per_page = settings.page_size
    total = db.scalar(
        select(func.count(InventoryMovement.id)).where(InventoryMovement.product_id == product_id)
    ) or 0
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    movements = db.scalars(
        select(InventoryMovement)
        .options(joinedload(InventoryMovement.user), joinedload(InventoryMovement.warehouse))
        .where(InventoryMovement.product_id == product_id)
        .order_by(InventoryMovement.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).all()

    return templates.TemplateResponse(
        request,
        "products/detail.html",
        tmpl_ctx(request, current_user, product=product, stock_levels=stock_levels,
                 movements=movements, page=page, total_pages=total_pages),
    )


@router.get("/{product_id}/edit")
def edit_product_page(
    product_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)
    if not product:
        return RedirectResponse(url="/products", status_code=303)
    categories = db.scalars(select(Category).order_by(Category.name)).all()
    return templates.TemplateResponse(
        request,
        "products/form.html",
        tmpl_ctx(request, current_user, product=product, categories=categories, error=None),
    )


@router.post("/{product_id}/edit")
async def edit_product(
    product_id: int,
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    category_id: str = Form(""),
    unit: str = Form("pcs"),
    cost_price: float = Form(0),
    reorder_point: int = Form(0),
    is_active: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    product = db.get(Product, product_id)
    if not product:
        return RedirectResponse(url="/products", status_code=303)

    product.name = name.strip()
    product.description = description.strip()
    product.category_id = int(category_id) if category_id else None
    product.unit = unit.strip() or "pcs"
    product.cost_price = cost_price
    product.reorder_point = reorder_point
    product.is_active = bool(is_active)
    db.commit()
    flash(request, f"商品「{product.name}」已更新。", "success")
    return RedirectResponse(url=f"/products/{product_id}", status_code=303)


@router.post("/{product_id}/deactivate")
async def deactivate_product(
    product_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    product = db.get(Product, product_id)
    if product:
        product.is_active = not product.is_active
        db.commit()
        status = "已啟用" if product.is_active else "已停用"
        flash(request, f"商品「{product.name}」{status}。", "success")
    return RedirectResponse(url="/products", status_code=303)
