"""Role and permission models."""
from __future__ import annotations

from datetime import datetime

from beanie import Document, Indexed
from pydantic import BaseModel, Field, field_validator

from app.rbac import SYSTEM_MODULES

MODULE_KEYS = {m["key"] for m in SYSTEM_MODULES}


class PermissionSet(BaseModel):
    view: bool = False
    add: bool = False
    edit: bool = False
    delete: bool = False


class Role(Document):
    key: Indexed(str, unique=True)
    name: str
    description: str | None = None
    is_active: bool = True
    is_default: bool = False
    permissions: dict[str, PermissionSet] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: dict[str, PermissionSet]) -> dict[str, PermissionSet]:
        unknown_modules = [k for k in value.keys() if k not in MODULE_KEYS]
        if unknown_modules:
            raise ValueError(f"Unsupported modules in permissions: {unknown_modules}")
        return value

    class Settings:
        name = "roles"
        use_state_management = True


class RolePermissionInput(BaseModel):
    module: str
    view: bool = False
    add: bool = False
    edit: bool = False
    delete: bool = False

    @field_validator("module")
    @classmethod
    def validate_module(cls, value: str) -> str:
        if value not in MODULE_KEYS:
            raise ValueError(f"Unsupported module: {value}")
        return value


class RoleCreateRequest(BaseModel):
    name: str
    description: str | None = None
    is_active: bool = True
    permissions: list[RolePermissionInput] = Field(default_factory=list)


class RoleUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    permissions: list[RolePermissionInput] | None = None


class RoleResponse(BaseModel):
    id: str
    key: str
    name: str
    description: str | None = None
    is_active: bool
    is_default: bool
    editable: bool
    permissions: list[RolePermissionInput]

