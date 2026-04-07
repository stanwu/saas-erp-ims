from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, engine
from app.models import User, UserRole
from app.security import hash_password


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def seed_admin(db: Session) -> None:
    settings = get_settings()
    existing_admin = db.scalar(select(User).where(User.username == settings.admin_username))
    if existing_admin:
        return

    admin = User(
        username=settings.admin_username,
        email=settings.admin_email,
        password_hash=hash_password(settings.admin_password),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    db.commit()
