from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import InventoryMovement, MovementType, Product, User
from app.services import apply_inventory_movement
from app.templates import templates


router = APIRouter(prefix="/movements", tags=["movements"])


@router.get("")
def list_movements(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    movements = db.scalars(
        select(InventoryMovement)
        .options(joinedload(InventoryMovement.product), joinedload(InventoryMovement.user))
        .order_by(InventoryMovement.created_at.desc())
    ).all()
    return templates.TemplateResponse(
        request,
        "movements.html",
        {"current_user": current_user, "movements": movements},
    )


@router.get("/new")
def new_movement_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    products = db.scalars(select(Product).order_by(Product.name.asc())).all()
    return templates.TemplateResponse(
        request,
        "movement_form.html",
        {
            "current_user": current_user,
            "products": products,
            "movement_types": list(MovementType),
            "error": None,
            "form": {},
        },
    )


@router.post("/new")
def create_movement(
    request: Request,
    product_id: int = Form(...),
    movement_type: str = Form(...),
    quantity: int = Form(...),
    note: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    products = db.scalars(select(Product).order_by(Product.name.asc())).all()
    product = db.get(Product, product_id)
    if not product:
        return templates.TemplateResponse(
            request,
            "movement_form.html",
            {
                "current_user": current_user,
                "products": products,
                "movement_types": list(MovementType),
                "error": "Product not found.",
                "form": {"product_id": product_id, "movement_type": movement_type, "quantity": quantity, "note": note},
            },
            status_code=400,
        )

    try:
        movement_enum = MovementType(movement_type)
        apply_inventory_movement(
            db,
            product=product,
            actor=current_user,
            movement_type=movement_enum,
            quantity=quantity,
            note=note,
        )
    except ValueError as exc:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "movement_form.html",
            {
                "current_user": current_user,
                "products": products,
                "movement_types": list(MovementType),
                "error": str(exc),
                "form": {"product_id": product_id, "movement_type": movement_type, "quantity": quantity, "note": note},
            },
            status_code=400,
        )

    return RedirectResponse(url="/movements", status_code=303)
