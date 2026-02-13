"""Beanie document models and Pydantic schemas."""
from app.models.user import User, UserRole, UserCreate, UserInDB
from app.models.student import Student, StudentCreate, AttendanceLog
from app.models.activity import Activity, ActivityCreate
from app.models.billing import Billing, FeeStructure, PaymentStatus, BillingCreate
from app.models.branch import Branch, BranchCreate, BranchUpdate, CCTVConfig
from app.models.settings import AppSettings, ClassOptionsUpdate, FeeComponent, FeeStructureItem, FeeStructuresUpdate
from app.models.feed import FeedPost, FeedPostCreate
from app.models.school_class import SchoolClass
from app.models.attendance import AttendanceRecord
from app.models.holiday import Holiday, HolidayCreate, HolidayUpdate, HolidayOut
from app.models.academic_year import AcademicYear, AcademicYearUpdate, AcademicYearConfigUpdate
from app.models.gallery import Album, Photo, AlbumCreate, AlbumUpdate
from app.models.role import Role, PermissionSet, RoleCreateRequest, RoleUpdateRequest, RoleResponse

__all__ = [
    "User",
    "UserRole",
    "UserCreate",
    "UserInDB",
    "Student",
    "StudentCreate",
    "AttendanceLog",
    "Activity",
    "ActivityCreate",
    "Billing",
    "FeeStructure",
    "PaymentStatus",
    "BillingCreate",
    "Branch",
    "BranchCreate",
    "BranchUpdate",
    "CCTVConfig",
    "AppSettings",
    "ClassOptionsUpdate",
    "FeeComponent",
    "FeeStructureItem",
    "FeeStructuresUpdate",
    "FeedPost",
    "FeedPostCreate",
    "SchoolClass",
    "AttendanceRecord",
    "Holiday",
    "HolidayCreate",
    "HolidayUpdate",
    "HolidayOut",
    "AcademicYear",
    "AcademicYearUpdate",
    "AcademicYearConfigUpdate",
    "Album",
    "Photo",
    "AlbumCreate",
    "AlbumUpdate",
    "Role",
    "PermissionSet",
    "RoleCreateRequest",
    "RoleUpdateRequest",
    "RoleResponse",
]
