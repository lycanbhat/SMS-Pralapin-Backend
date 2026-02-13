"""RBAC: Admins, Teachers, Parents."""
from datetime import datetime
from enum import Enum
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    ADMIN = "admin"
    COORDINATOR = "coordinator"
    FACULTY = "faculty"
    TEACHER = "teacher"
    PARENT = "parent"


class User(Document):
    """User document for RBAC across Admin, Teacher, Parent."""

    email: Indexed(EmailStr, unique=True)
    hashed_password: str
    role: UserRole
    full_name: str
    phone: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Parent-specific: linked student IDs
    student_ids: list[str] = Field(default_factory=list)

    # Teacher-specific: branch/class assignments
    branch_id: Optional[str] = None
    assigned_class_ids: list[str] = Field(default_factory=list)

    # FCM tokens for notifications
    fcm_tokens: list[str] = Field(default_factory=list)

    class Settings:
        name = "users"
        use_state_management = True


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: UserRole
    full_name: str
    phone: Optional[str] = None
    student_ids: list[str] = Field(default_factory=list)
    branch_id: Optional[str] = None
    assigned_class_ids: list[str] = Field(default_factory=list)


class UserInDB(BaseModel):
    id: str
    email: str
    role: UserRole
    full_name: str
    phone: Optional[str] = None
    is_active: bool
    student_ids: list[str] = []
    branch_id: Optional[str] = None
    assigned_class_ids: list[str] = []

    class Config:
        from_attributes = True
