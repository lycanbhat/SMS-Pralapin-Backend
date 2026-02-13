"""RBAC module/action registry and defaults."""
from __future__ import annotations

from typing import Literal

PermissionAction = Literal["view", "add", "edit", "delete"]

ACTION_BY_METHOD: dict[str, PermissionAction] = {
    "GET": "view",
    "HEAD": "view",
    "OPTIONS": "view",
    "POST": "add",
    "PUT": "edit",
    "PATCH": "edit",
    "DELETE": "delete",
}

SYSTEM_MODULES: list[dict[str, str]] = [
    {"key": "dashboard", "name": "Dashboard"},
    {"key": "students", "name": "Students"},
    {"key": "attendance", "name": "Attendance"},
    {"key": "staff", "name": "Staff"},
    {"key": "feed", "name": "Announcements"},
    {"key": "gallery", "name": "Gallery"},
    {"key": "holidays", "name": "Holidays"},
    {"key": "branches", "name": "Branches"},
    {"key": "billing", "name": "Billing"},
    {"key": "activities", "name": "Activities"},
    {"key": "settings", "name": "Settings"},
    {"key": "users", "name": "Users"},
    {"key": "roles_permissions", "name": "Roles & Permissions"},
    {"key": "mobile", "name": "Mobile"},
    {"key": "cctv", "name": "CCTV"},
]


def _full_permissions() -> dict[str, bool]:
    return {"view": True, "add": True, "edit": True, "delete": True}


def _view_only() -> dict[str, bool]:
    return {"view": True, "add": False, "edit": False, "delete": False}


def _module_defaults(fill: dict[str, bool]) -> dict[str, dict[str, bool]]:
    return {module["key"]: dict(fill) for module in SYSTEM_MODULES}


DEFAULT_ROLE_PERMISSIONS: dict[str, dict[str, dict[str, bool]]] = {
    "admin": _module_defaults(_full_permissions()),
    "coordinator": {
        **_module_defaults({"view": False, "add": False, "edit": False, "delete": False}),
        "dashboard": _view_only(),
        "students": {"view": True, "add": True, "edit": True, "delete": False},
        "attendance": {"view": True, "add": True, "edit": True, "delete": False},
        "holidays": {"view": True, "add": True, "edit": True, "delete": False},
        "feed": {"view": True, "add": True, "edit": True, "delete": False},
        "gallery": {"view": True, "add": True, "edit": True, "delete": False},
        "branches": _view_only(),
        "settings": _view_only(),
    },
    "faculty": {
        **_module_defaults({"view": False, "add": False, "edit": False, "delete": False}),
        "dashboard": _view_only(),
        "students": {"view": True, "add": True, "edit": True, "delete": False},
        "attendance": {"view": True, "add": True, "edit": True, "delete": False},
        "feed": {"view": True, "add": True, "edit": False, "delete": False},
        "gallery": {"view": True, "add": True, "edit": True, "delete": False},
        "activities": {"view": True, "add": True, "edit": False, "delete": False},
        "holidays": _view_only(),
        "branches": _view_only(),
    },
    "teacher": {
        **_module_defaults({"view": False, "add": False, "edit": False, "delete": False}),
        "dashboard": _view_only(),
        "students": {"view": True, "add": True, "edit": True, "delete": False},
        "attendance": {"view": True, "add": True, "edit": True, "delete": False},
        "feed": {"view": True, "add": True, "edit": False, "delete": False},
        "gallery": {"view": True, "add": True, "edit": True, "delete": False},
        "activities": {"view": True, "add": True, "edit": False, "delete": False},
        "holidays": _view_only(),
        "branches": _view_only(),
    },
    "parent": {
        **_module_defaults({"view": False, "add": False, "edit": False, "delete": False}),
        "dashboard": _view_only(),
        "students": _view_only(),
        "attendance": _view_only(),
        "feed": _view_only(),
        "gallery": _view_only(),
        "holidays": _view_only(),
        "billing": _view_only(),
        "mobile": _view_only(),
        "cctv": _view_only(),
    },
}
