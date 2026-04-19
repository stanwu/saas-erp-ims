from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import flash, generate_csrf_token, validate_csrf
from app.services import authenticate_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def root():
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/login")
def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard", status_code=303)
    csrf_token = generate_csrf_token(request)
    return templates.TemplateResponse(request, "auth/login.html", {"csrf_token": csrf_token, "error": None})


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    from app.dependencies import validate_csrf
    try:
        validate_csrf(request, csrf_token)
    except Exception:
        new_csrf = generate_csrf_token(request)
        return templates.TemplateResponse(
            request, "auth/login.html",
            {"csrf_token": new_csrf, "error": "請求無效，請再試一次。"},
            status_code=403,
        )

    user = authenticate_user(db, username, password)
    if not user:
        new_csrf = generate_csrf_token(request)
        return templates.TemplateResponse(
            request, "auth/login.html",
            {"csrf_token": new_csrf, "error": "帳號或密碼錯誤。"},
            status_code=401,
        )

    request.session.clear()
    request.session["user_id"] = user.id
    flash(request, f"歡迎回來，{user.username}！", "success")
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/logout")
def logout(
    request: Request,
    _: None = Depends(validate_csrf),
):
    request.session.clear()
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session")
    return response
