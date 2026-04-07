from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_role
from app.models import User, UserRole
from app.security import hash_password
from app.templates import templates


router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
def list_users(
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    return templates.TemplateResponse(
        request,
        "users.html",
        {"current_user": current_user, "users": users, "roles": list(UserRole), "error": None},
    )


@router.post("")
def create_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    is_active: bool = Form(False),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        user_role = UserRole(role)
    except ValueError:
        users = db.scalars(select(User).order_by(User.created_at.desc())).all()
        return templates.TemplateResponse(
            request,
            "users.html",
            {
                "current_user": current_user,
                "users": users,
                "roles": list(UserRole),
                "error": "Invalid role.",
            },
            status_code=400,
        )

    if len(password) < 8:
        users = db.scalars(select(User).order_by(User.created_at.desc())).all()
        return templates.TemplateResponse(
            request,
            "users.html",
            {
                "current_user": current_user,
                "users": users,
                "roles": list(UserRole),
                "error": "Password must be at least 8 characters.",
            },
            status_code=400,
        )

    user = User(
        username=username.strip(),
        email=email.strip(),
        password_hash=hash_password(password),
        role=user_role,
        is_active=is_active,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        users = db.scalars(select(User).order_by(User.created_at.desc())).all()
        return templates.TemplateResponse(
            request,
            "users.html",
            {
                "current_user": current_user,
                "users": users,
                "roles": list(UserRole),
                "error": "Username and email must be unique.",
            },
            status_code=400,
        )

    return RedirectResponse(url="/users", status_code=303)
