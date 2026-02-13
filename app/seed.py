"""Seed default admin user if not present."""
from app.models.user import User, UserRole
from app.api.deps import get_password_hash

ADMIN_EMAIL = "admin@pralapin.com"
ADMIN_PASSWORD = "Inchara123##"
ADMIN_FULL_NAME = "Pralapin Admin"


async def seed_admin():
    existing = await User.find_one(User.email == ADMIN_EMAIL)
    if existing:
        return
    await User(
        email=ADMIN_EMAIL,
        hashed_password=get_password_hash(ADMIN_PASSWORD),
        role=UserRole.ADMIN,
        full_name=ADMIN_FULL_NAME,
    ).insert()
