import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


TEST_DB = Path(__file__).resolve().parent / "test_erp_ims.db"
os.environ["ERP_IMS_DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["ERP_IMS_SECRET_KEY"] = "test-secret"
os.environ["ERP_IMS_CSRF_SECRET"] = "test-csrf-secret"
os.environ["ERP_IMS_ADMIN_USERNAME"] = "admin"
os.environ["ERP_IMS_ADMIN_PASSWORD"] = "admin@12345"
os.environ["ERP_IMS_ENV"] = "test"

from app.main import app  # noqa: E402
from app.config import Settings, get_settings  # noqa: E402


def _get_csrf(client: TestClient) -> str:
    resp = client.get("/login")
    import re
    match = re.search(r'name="csrf_token" value="([^"]+)"', resp.text)
    return match.group(1) if match else ""


def _login_admin(client: TestClient) -> None:
    csrf = _get_csrf(client)
    resp = client.post(
        "/login",
        data={"username": "admin", "password": "admin@12345", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_dashboard_redirects_to_login_when_anonymous():
    with TestClient(app) as client:
        resp = client.get("/dashboard", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/login"


def test_login_rotates_session_and_sets_samesite_cookie():
    with TestClient(app) as client:
        csrf = _get_csrf(client)
        resp = client.post(
            "/login",
            data={"username": "admin", "password": "admin@12345", "csrf_token": csrf},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        set_cookie = resp.headers.get("set-cookie", "").lower()
        assert "session=" in set_cookie
        assert "samesite=lax" in set_cookie


def test_logout_rejects_anonymous_csrf_token_after_login():
    with TestClient(app) as client:
        anonymous_csrf = _get_csrf(client)
        _login_admin(client)

        resp = client.post(
            "/logout",
            data={"csrf_token": anonymous_csrf},
            follow_redirects=False,
        )
        assert resp.status_code == 403

        dashboard = client.get("/dashboard", follow_redirects=False)
        assert dashboard.status_code == 200


def test_production_settings_reject_default_session_secrets(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ERP_IMS_ENV", "production")
    monkeypatch.setenv("ERP_IMS_SECRET_KEY", "dev-secret-key-change-in-prod")
    monkeypatch.setenv("ERP_IMS_CSRF_SECRET", "csrf-secret-change-in-prod")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="ERP_IMS_SECRET_KEY"):
            Settings()
    finally:
        get_settings.cache_clear()
        monkeypatch.setenv("ERP_IMS_ENV", "test")
        monkeypatch.setenv("ERP_IMS_SECRET_KEY", "test-secret")
        monkeypatch.setenv("ERP_IMS_CSRF_SECRET", "test-csrf-secret")


def test_production_settings_accept_custom_secrets(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ERP_IMS_ENV", "production")
    monkeypatch.setenv("ERP_IMS_SECRET_KEY", "prod-session-secret-123")
    monkeypatch.setenv("ERP_IMS_CSRF_SECRET", "prod-csrf-secret-456")
    get_settings.cache_clear()
    try:
        settings = Settings()
        assert settings.is_production_like is True
        assert settings.session_https_only is True
    finally:
        get_settings.cache_clear()
        monkeypatch.setenv("ERP_IMS_ENV", "test")
        monkeypatch.setenv("ERP_IMS_SECRET_KEY", "test-secret")
        monkeypatch.setenv("ERP_IMS_CSRF_SECRET", "test-csrf-secret")
