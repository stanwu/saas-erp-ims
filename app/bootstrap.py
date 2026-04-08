from sqlalchemy import select
from sqlalchemy.orm import Session

from app.demo_seed import seed_demo_data, should_seed_demo_data
from app.config import get_settings
from app.database import Base, engine
from app.models import Category, User, UserRole, Warehouse
from app.security import hash_password


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def seed_initial_data(db: Session) -> None:
    settings = get_settings()

    if not db.scalar(select(User).where(User.username == settings.admin_username)):
        admin = User(
            username=settings.admin_username,
            password_hash=hash_password(settings.admin_password),
            role=UserRole.admin,
            is_active=True,
        )
        db.add(admin)

    if not db.scalar(select(Warehouse).where(Warehouse.name == "Main Warehouse")):
        db.add(Warehouse(name="Main Warehouse", location="Default", is_active=True))

    if not db.scalar(select(Category).where(Category.name == "General")):
        db.add(Category(name="General", description="General category"))

    db.commit()

    if should_seed_demo_data(db):
        seed_demo_data(db)
