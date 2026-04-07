from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import InventoryMovement, Product, User, UserRole
from app.templates import templates


router = APIRouter(prefix="/products", tags=["products"])


@router.get("")
def list_products(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    products = db.scalars(select(Product).order_by(Product.created_at.desc())).all()
    return templates.TemplateResponse(
        request,
        "products.html",
        {"current_user": current_user, "products": products},
    )


@router.get("/new")
def new_product_page(
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    return templates.TemplateResponse(
        request,
        "product_form.html",
        {"current_user": current_user, "error": None, "form": {}},
    )


@router.post("/new")
def create_product(
    request: Request,
    sku: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    unit: str = Form(...),
    is_active: bool = Form(False),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    product = Product(
        sku=sku.strip(),
        name=name.strip(),
        description=description.strip(),
        unit=unit.strip(),
        is_active=is_active,
    )
    db.add(product)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "product_form.html",
            {
                "current_user": current_user,
                "error": "SKU must be unique.",
                "form": {
                    "sku": sku,
                    "name": name,
                    "description": description,
                    "unit": unit,
                    "is_active": is_active,
                },
            },
            status_code=400,
        )
    return RedirectResponse(url="/products", status_code=303)


@router.get("/{product_id}")
def product_detail(
    product_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = db.scalar(
        select(Product)
        .options(selectinload(Product.movements).selectinload(InventoryMovement.user))
        .where(Product.id == product_id)
    )
    if not product:
        return RedirectResponse(url="/products", status_code=303)
    movements = sorted(product.movements, key=lambda item: item.created_at, reverse=True)
    return templates.TemplateResponse(
        request,
        "product_detail.html",
        {"current_user": current_user, "product": product, "movements": movements},
    )
