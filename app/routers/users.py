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
from app.models import User, UserRole
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


@router.get("")
def list_users(
    request: Request,
    page: int = 1,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    per_page = settings.page_size
    total = db.scalar(select(func.count(User.id))) or 0
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    users = db.scalars(
        select(User).order_by(User.created_at.desc())
        .offset((page - 1) * per_page).limit(per_page)
    ).all()
    return templates.TemplateResponse(
        request,
        "users/list.html",
        tmpl_ctx(request, current_user, users=users, page=page, total_pages=total_pages, total=total),
    )


@router.get("/new")
def new_user_page(
    request: Request,
    current_user: User = Depends(require_admin),
):
    return templates.TemplateResponse(
        request,
        "users/form.html",
        tmpl_ctx(request, current_user, user=None, roles=list(UserRole), error=None),
    )


@router.post("/new")
async def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form("staff"),
    is_active: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    if len(password) < 8:
        return templates.TemplateResponse(
            request,
            "users/form.html",
            tmpl_ctx(request, current_user, user=None, roles=list(UserRole),
                     error="密碼至少需要 8 個字元。"),
            status_code=400,
        )
    user = User(
        username=username.strip(),
        password_hash=hash_password(password),
        role=UserRole(role),
        is_active=bool(is_active),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "users/form.html",
            tmpl_ctx(request, current_user, user=None, roles=list(UserRole),
                     error="此帳號已存在。"),
            status_code=400,
        )
    flash(request, f"使用者「{username}」已建立。", "success")
    return RedirectResponse(url="/users", status_code=303)


@router.get("/{user_id}/edit")
def edit_user_page(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        return RedirectResponse(url="/users", status_code=303)
    return templates.TemplateResponse(
        request,
        "users/form.html",
        tmpl_ctx(request, current_user, user=user, roles=list(UserRole), error=None),
    )


@router.post("/{user_id}/edit")
async def edit_user(
    user_id: int,
    request: Request,
    role: str = Form(...),
    is_active: str = Form(""),
    new_password: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    user = db.get(User, user_id)
    if not user:
        return RedirectResponse(url="/users", status_code=303)
    user.role = UserRole(role)
    user.is_active = bool(is_active)
    if new_password:
        if len(new_password) < 8:
            return templates.TemplateResponse(
                request,
                "users/form.html",
                tmpl_ctx(request, current_user, user=user, roles=list(UserRole),
                         error="密碼至少需要 8 個字元。"),
                status_code=400,
            )
        user.password_hash = hash_password(new_password)
    db.commit()
    flash(request, f"使用者「{user.username}」已更新。", "success")
    return RedirectResponse(url="/users", status_code=303)


@router.post("/{user_id}/toggle")
async def toggle_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    user = db.get(User, user_id)
    if user and user.id != current_user.id:
        user.is_active = not user.is_active
        db.commit()
        status = "已啟用" if user.is_active else "已停用"
        flash(request, f"使用者「{user.username}」{status}。", "success")
    return RedirectResponse(url="/users", status_code=303)
