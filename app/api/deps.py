"""Shared dependencies: JWT auth, role checks and permissions."""
from datetime import datetime, timedelta
from typing import Annotated, Optional

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer
from jose import JWTError, jwt

from app.config import settings
from app.models.role import Role
from app.models.user import User, UserRole
from app.rbac import ACTION_BY_METHOD, PermissionAction
from app.services.roles import has_permission
from beanie import PydanticObjectId

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
security = HTTPBearer(auto_error=False)


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(subject: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    to_encode = {"sub": subject, "role": role, "exp": expire, "type": "access"}
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


async def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = await User.get(PydanticObjectId(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_roles(*allowed: UserRole):
    allowed_values = [role.value for role in allowed]

    async def checker(user: Annotated[User, Depends(get_current_user)]):
        if user.role not in allowed_values:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return checker


async def get_current_role(user: Annotated[User, Depends(get_current_user)]) -> Role | None:
    return await Role.find_one(Role.key == user.role)


def require_permission(module: str, action: PermissionAction):
    async def checker(
        user: Annotated[User, Depends(get_current_user)],
        role: Annotated[Role | None, Depends(get_current_role)],
    ):
        if not has_permission(role, module, action):
            raise HTTPException(status_code=403, detail=f"Missing {module}.{action} permission")
        return user

    return checker


def require_module_permission(module: str):
    async def checker(
        request: Request,
        user: Annotated[User, Depends(get_current_user)],
        role: Annotated[Role | None, Depends(get_current_role)],
    ):
        method = request.method.upper()
        action = ACTION_BY_METHOD.get(method)
        if not action:
            raise HTTPException(status_code=405, detail=f"Unsupported method for permission check: {method}")
        if not has_permission(role, module, action):
            raise HTTPException(status_code=403, detail=f"Missing {module}.{action} permission")
        return user

    return checker


# Type aliases for route injection
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentRole = Annotated[Role | None, Depends(get_current_role)]
AdminOnly = Annotated[User, Depends(get_current_user)]
StaffOnly = Annotated[User, Depends(get_current_user)]
TeacherOrAdmin = Annotated[User, Depends(get_current_user)]
ParentOnly = Annotated[User, Depends(require_roles(UserRole.PARENT))]
