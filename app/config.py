from functools import lru_cache
from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    def __init__(self) -> None:
        self.app_name = "ERP IMS"
        self.secret_key = os.getenv("ERP_IMS_SECRET_KEY", "dev-secret-key-change-in-prod")
        self.csrf_secret = os.getenv("ERP_IMS_CSRF_SECRET", "csrf-secret-change-in-prod")
        self.database_url = os.getenv(
            "ERP_IMS_DATABASE_URL",
            f"sqlite:///{BASE_DIR / 'erp_ims.db'}",
        )
        self.admin_username = os.getenv("ERP_IMS_ADMIN_USERNAME", "admin")
        self.admin_password = os.getenv("ERP_IMS_ADMIN_PASSWORD", "admin12345")
        self.page_size: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
