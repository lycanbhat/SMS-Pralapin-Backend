"""JWT-based stateless authentication."""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_password_hash, create_access_token, get_current_user, CurrentUser
from app.models.user import User, UserRole, UserCreate
from beanie import PydanticObjectId

router = APIRouter()


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class FCMTokenRequest(BaseModel):
    token: str


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    user = await User.find_one(User.email == req.email)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    from app.api.deps import verify_password, create_refresh_token
    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(str(user.id), user.role.value)
    refresh_token = create_refresh_token(str(user.id))
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/register", response_model=TokenResponse)
async def register(data: UserCreate):
    existing = await User.find_one(User.email == data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    from app.api.deps import create_refresh_token
    user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        role=data.role,
        full_name=data.full_name,
        phone=data.phone,
        student_ids=data.student_ids,
        branch_id=data.branch_id,
        assigned_class_ids=data.assigned_class_ids,
    )
    await user.insert()
    access_token = create_access_token(str(user.id), user.role.value)
    refresh_token = create_refresh_token(str(user.id))
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(req: RefreshRequest):
    from jose import jwt, JWTError
    from app.config import settings
    try:
        payload = jwt.decode(req.refresh_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Expired or invalid refresh token")

    user = await User.get(PydanticObjectId(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    from app.api.deps import create_refresh_token
    new_access = create_access_token(str(user.id), user.role.value)
    new_refresh = create_refresh_token(str(user.id))
    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.get("/me")
async def me(user: CurrentUser):
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "full_name": user.full_name,
        "student_ids": user.student_ids,
        "branch_id": user.branch_id,
        "assigned_class_ids": user.assigned_class_ids,
    }


@router.post("/fcm-token")
async def register_fcm_token(req: FCMTokenRequest, user: CurrentUser):
    if req.token not in user.fcm_tokens:
        user.fcm_tokens.append(req.token)
        # Limit tokens per user to 5 to prevent bloat
        if len(user.fcm_tokens) > 5:
            user.fcm_tokens = user.fcm_tokens[-5:]
        await user.save()
    return {"status": "ok"}
