from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from beanie import PydanticObjectId
from pydantic import BaseModel, EmailStr

from app.api.deps import AdminOnly, get_password_hash
from app.models.user import User, UserRole, UserInDB

router = APIRouter()

class StaffCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str
    branch_id: Optional[str] = None
    assigned_class_ids: List[str] = []

class StaffUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    branch_id: Optional[str] = None
    assigned_class_ids: Optional[List[str]] = None
    is_active: Optional[bool] = None

@router.get("/")
async def list_staff(admin: AdminOnly):
    """List all staff members (every role except parent)."""
    staff = await User.find({"role": {"$ne": UserRole.PARENT.value}}).to_list()
    return [
        {
            "id": str(s.id),
            "email": s.email,
            "role": s.role,
            "full_name": s.full_name,
            "phone": s.phone,
            "is_active": s.is_active,
            "branch_id": s.branch_id,
            "assigned_class_ids": s.assigned_class_ids,
        }
        for s in staff
    ]


@router.post("/", response_model=UserInDB)
async def create_staff(data: StaffCreate, admin: AdminOnly):
    """Create a new staff member."""
    existing = await User.find_one(User.email == data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        role=data.role,
        full_name=data.full_name,
        branch_id=data.branch_id,
        assigned_class_ids=data.assigned_class_ids,
    )
    await user.insert()
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
        "full_name": user.full_name,
        "phone": user.phone,
        "is_active": user.is_active,
        "branch_id": user.branch_id,
        "assigned_class_ids": user.assigned_class_ids,
    }


@router.get("/{staff_id}")
async def get_staff(staff_id: str, admin: AdminOnly):
    """Get staff details."""
    user = await User.get(PydanticObjectId(staff_id))
    if not user:
        raise HTTPException(status_code=404, detail="Staff member not found")
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
        "full_name": user.full_name,
        "phone": user.phone,
        "is_active": user.is_active,
        "branch_id": user.branch_id,
        "assigned_class_ids": user.assigned_class_ids,
    }


@router.patch("/{staff_id}")
async def update_staff(staff_id: str, data: StaffUpdate, admin: AdminOnly):
    """Update staff details."""
    user = await User.get(PydanticObjectId(staff_id))
    if not user:
        raise HTTPException(status_code=404, detail="Staff member not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)

    await user.save()
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
        "full_name": user.full_name,
        "phone": user.phone,
        "is_active": user.is_active,
        "branch_id": user.branch_id,
        "assigned_class_ids": user.assigned_class_ids,
    }

@router.delete("/{staff_id}", status_code=204)
async def delete_staff(staff_id: str, admin: AdminOnly):
    """Soft delete staff member."""
    user = await User.get(PydanticObjectId(staff_id))
    if not user:
        raise HTTPException(status_code=404, detail="Staff member not found")
    user.is_active = False
    user.role = ""
    user.branch_id = None
    user.assigned_class_ids = []
    await user.save()
