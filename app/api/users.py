"""User CRUD - RBAC management."""
from fastapi import APIRouter, HTTPException
from beanie import PydanticObjectId

from app.api.deps import AdminOnly
from app.models.user import User, UserCreate
from app.api.deps import get_password_hash
from pydantic import BaseModel

router = APIRouter()


class PasswordUpdate(BaseModel):
    password: str


@router.get("/")
async def list_users(user: AdminOnly):
    users = await User.find_all().to_list()
    return [{"id": str(u.id), "email": u.email, "role": u.role, "full_name": u.full_name} for u in users]


@router.post("/", status_code=201)
async def create_user(data: UserCreate, admin: AdminOnly):
    existing = await User.find_one(User.email == data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    u = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        role=data.role,
        full_name=data.full_name,
        phone=data.phone,
        student_ids=data.student_ids,
        branch_id=data.branch_id,
        assigned_class_ids=data.assigned_class_ids,
    )
    await u.insert()
    return {"id": str(u.id), "email": u.email, "role": u.role}


@router.post("/{user_id}/set-password")
async def set_user_password(user_id: str, data: PasswordUpdate, admin: AdminOnly):
    """Set or reset a user's password (admin-only)."""
    u = await User.get(PydanticObjectId(user_id))
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    u.hashed_password = get_password_hash(data.password)
    await u.save()
    return {"id": str(u.id)}
