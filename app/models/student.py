"""Centralized child info, class assignments, attendance logs."""
from datetime import date, datetime
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field


class AttendanceLog(BaseModel):
    date: date
    status: str  # present, absent, late, leave
    marked_at: datetime
    marked_by: str  # user_id


class GuardianInfo(BaseModel):
    name: str
    relationship: str  # Mother, Father, other
    relationship_other: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class EmergencyContact(BaseModel):
    name: str
    relationship: str
    phone: str


class Student(Document):
    """Student document: child info, class, attendance."""

    full_name: str
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None

    parent_user_id: str = ""  # optional; primary guardian may link to user
    branch_id: Indexed(str)
    class_id: str
    class_name: Optional[str] = None
    roll_number: Optional[str] = None
    academic_year: Optional[str] = None  # e.g. 2024-25, auto on create
    admission_number: Optional[str] = None  # auto per branch on create

    primary_guardian: Optional[GuardianInfo] = None
    secondary_guardian: Optional[GuardianInfo] = None
    emergency_contact: Optional[EmergencyContact] = None

    photo_url: Optional[str] = None  # student photo URL (uploaded document)

    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    attendance_logs: list[AttendanceLog] = Field(default_factory=list)

    class Settings:
        name = "students"
        use_state_management = True


class GuardianInfoCreate(BaseModel):
    name: str
    relationship: str  # Mother, Father, other
    relationship_other: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class EmergencyContactCreate(BaseModel):
    name: str
    relationship: str
    phone: str


class StudentCreate(BaseModel):
    full_name: str
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None

    branch_id: str
    class_id: str
    class_name: Optional[str] = None
    roll_number: Optional[str] = None
    parent_user_id: Optional[str] = None

    primary_guardian: Optional[GuardianInfoCreate] = None
    secondary_guardian: Optional[GuardianInfoCreate] = None
    emergency_contact: Optional[EmergencyContactCreate] = None


class StudentUpdate(BaseModel):
    """All fields optional for PATCH; academic_year and admission_number are not updatable."""
    full_name: Optional[str] = None
    photo_url: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    branch_id: Optional[str] = None
    class_id: Optional[str] = None
    class_name: Optional[str] = None
    roll_number: Optional[str] = None
    parent_user_id: Optional[str] = None
    primary_guardian: Optional[GuardianInfoCreate] = None
    secondary_guardian: Optional[GuardianInfoCreate] = None
    emergency_contact: Optional[EmergencyContactCreate] = None
