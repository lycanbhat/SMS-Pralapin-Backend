"""Role lifecycle helpers and permission checks."""
from __future__ import annotations

from datetime import datetime
import re

from app.config import settings
from app.models.role import PermissionSet, Role, RolePermissionInput, RoleResponse
from app.rbac import DEFAULT_ROLE_PERMISSIONS, SYSTEM_MODULES


def slugify_role_key(name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    if not key:
        key = "role"
    return key


def _permissions_map_from_inputs(items: list[RolePermissionInput]) -> dict[str, PermissionSet]:
    permissions_map: dict[str, PermissionSet] = {}
    for item in items:
        permissions_map[item.module] = PermissionSet(
            view=item.view,
            add=item.add,
            edit=item.edit,
            delete=item.delete,
        )
    return permissions_map


def _permissions_inputs_from_map(permissions: dict[str, PermissionSet]) -> list[RolePermissionInput]:
    outputs: list[RolePermissionInput] = []
    module_keys = [m["key"] for m in SYSTEM_MODULES]
    for module in module_keys:
        perm = permissions.get(module, PermissionSet())
        outputs.append(
            RolePermissionInput(
                module=module,
                view=perm.view,
                add=perm.add,
                edit=perm.edit,
                delete=perm.delete,
            )
        )
    return outputs


def can_edit_role(role: Role) -> bool:
    if not role.is_default:
        return True
    return settings.allow_edit_default_roles


def role_to_response(role: Role) -> RoleResponse:
    return RoleResponse(
        id=str(role.id),
        key=role.key,
        name=role.name,
        description=role.description,
        is_active=role.is_active,
        is_default=role.is_default,
        editable=can_edit_role(role),
        permissions=_permissions_inputs_from_map(role.permissions),
    )


def has_permission(role: Role | None, module: str, action: str) -> bool:
    if not role or not role.is_active:
        return False
    permission = role.permissions.get(module)
    if not permission:
        return False
    return bool(getattr(permission, action, False))


async def ensure_default_roles() -> None:
    """Ensure built-in roles exist and include current module keys."""
    module_keys = [m["key"] for m in SYSTEM_MODULES]
    for role_key, defaults in DEFAULT_ROLE_PERMISSIONS.items():
        role = await Role.find_one(Role.key == role_key)
        default_permissions: dict[str, PermissionSet] = {}
        for module in module_keys:
            conf = defaults.get(module, {"view": False, "add": False, "edit": False, "delete": False})
            default_permissions[module] = PermissionSet(**conf)

        if role:
            merged_permissions: dict[str, PermissionSet] = {}
            for module in module_keys:
                # Keep existing customized permissions; only backfill missing modules.
                merged_permissions[module] = role.permissions.get(module, default_permissions[module])
            role.is_default = True
            role.permissions = merged_permissions
            role.name = role.name or role_key.replace("_", " ").title()
            role.updated_at = datetime.utcnow()
            await role.save()
            continue

        role = Role(
            key=role_key,
            name=role_key.replace("_", " ").title(),
            description=f"Default {role_key.replace('_', ' ').title()} role",
            is_active=True,
            is_default=True,
            permissions=default_permissions,
        )
        await role.insert()

