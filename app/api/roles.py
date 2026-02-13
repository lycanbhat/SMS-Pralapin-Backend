"""Dynamic roles and permissions API."""
from __future__ import annotations

from datetime import datetime

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException

from app.api.deps import AdminOnly
from app.models.role import Role, RoleCreateRequest, RoleUpdateRequest
from app.rbac import SYSTEM_MODULES
from app.services.roles import (
    can_edit_role,
    role_to_response,
    slugify_role_key,
    _permissions_map_from_inputs,
)

router = APIRouter()


@router.get("/modules")
async def list_modules(user: AdminOnly):
    return {"items": SYSTEM_MODULES}


@router.get("/")
async def list_roles(user: AdminOnly):
    roles = await Role.find_all().sort("name").to_list()
    return {"items": [role_to_response(role).model_dump() for role in roles]}


@router.get("/{role_id}")
async def get_role(role_id: str, user: AdminOnly):
    role = await Role.get(PydanticObjectId(role_id))
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role_to_response(role)


@router.post("/", status_code=201)
async def create_role(data: RoleCreateRequest, user: AdminOnly):
    key = slugify_role_key(data.name)
    existing = await Role.find_one(Role.key == key)
    if existing:
        raise HTTPException(status_code=400, detail="Role with same name already exists")

    role = Role(
        key=key,
        name=data.name.strip(),
        description=(data.description or "").strip() or None,
        is_active=data.is_active,
        is_default=False,
        permissions=_permissions_map_from_inputs(data.permissions),
    )
    await role.insert()
    return role_to_response(role)


@router.patch("/{role_id}")
async def update_role(role_id: str, data: RoleUpdateRequest, user: AdminOnly):
    role = await Role.get(PydanticObjectId(role_id))
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if not can_edit_role(role):
        raise HTTPException(status_code=403, detail="Editing default roles is disabled by system settings")

    update_data = data.model_dump(exclude_unset=True)
    if "name" in update_data:
        role.name = (update_data["name"] or "").strip() or role.name
    if "description" in update_data:
        role.description = ((update_data["description"] or "").strip() or None)
    if "is_active" in update_data:
        role.is_active = bool(update_data["is_active"])
    if "permissions" in update_data:
        role.permissions = _permissions_map_from_inputs(data.permissions or [])
    role.updated_at = datetime.utcnow()
    await role.save()
    return role_to_response(role)

