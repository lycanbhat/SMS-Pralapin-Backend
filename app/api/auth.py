"""JWT-based stateless authentication."""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_password_hash, create_access_token, get_current_user, CurrentUser
from app.models.role import PermissionSet, Role
from app.rbac import SYSTEM_MODULES
from app.models.user import User, UserCreate
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


class ParentOTPLoginRequest(BaseModel):
    id_token: str


@router.post("/parent/login-otp", response_model=TokenResponse)
async def parent_login_otp(req: ParentOTPLoginRequest):
    import firebase_admin.auth as firebase_auth
    from app.services.fcm import _get_firebase_app
    import re
    
    app = _get_firebase_app()
    if not app:
        raise HTTPException(
            status_code=500,
            detail="Firebase Authentication is not configured on the server."
        )
    
    try:
        decoded_token = firebase_auth.verify_id_token(req.id_token, app=app)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Firebase ID Token: {e}")
        
    phone_number = decoded_token.get("phone_number")
    if not phone_number:
        raise HTTPException(status_code=400, detail="Phone number not found in Firebase Token")
        
    def normalize_phone(p: str | None) -> str:
        if not p:
            return ""
        return re.sub(r"\D", "", p)
        
    norm_target = normalize_phone(phone_number)
    
    # Try exact match first
    user = await User.find_one(User.role == "parent", User.phone == phone_number)
    
    if not user:
        # Fallback 1: scan all active parents by normalized/suffix matching
        all_parents = await User.find(User.role == "parent", User.is_active == True).to_list()
        for p in all_parents:
            if p.phone:
                p_norm = normalize_phone(p.phone)
                if p_norm == norm_target:
                    user = p
                    break
                if len(p_norm) >= 10 and len(norm_target) >= 10:
                    if p_norm[-10:] == norm_target[-10:]:
                        user = p
                        break
                        
    if not user:
        # Fallback 2: check if the phone number belongs to a primary or secondary guardian of any student
        from app.models.student import Student as StudentModel
        all_students = await StudentModel.find(StudentModel.is_active == True).to_list()
        for s in all_students:
            for g in [s.primary_guardian, s.secondary_guardian]:
                if g and g.phone:
                    g_norm = normalize_phone(g.phone)
                    if g_norm == norm_target or (len(g_norm) >= 10 and len(norm_target) >= 10 and g_norm[-10:] == norm_target[-10:]):
                        if s.parent_user_id:
                            try:
                                user = await User.get(PydanticObjectId(s.parent_user_id))
                                if user:
                                    break
                            except Exception:
                                pass
            if user:
                break
                        
    if not user or not user.is_active:
        raise HTTPException(
            status_code=404, 
            detail=f"Parent account with phone number {phone_number} is not registered."
        )
        
    from app.api.deps import create_refresh_token
    access_token = create_access_token(str(user.id), user.role)
    refresh_token = create_refresh_token(str(user.id))
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    user = await User.find_one(User.email == req.email)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    from app.api.deps import verify_password, create_refresh_token
    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(str(user.id), user.role)
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
    access_token = create_access_token(str(user.id), user.role)
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
    new_access = create_access_token(str(user.id), user.role)
    new_refresh = create_refresh_token(str(user.id))
    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.get("/me")
async def me(user: CurrentUser):
    role = await Role.find_one(Role.key == user.role)
    module_keys = [m["key"] for m in SYSTEM_MODULES]
    permissions: dict[str, dict[str, bool]] = {}
    for module in module_keys:
        current = role.permissions.get(module) if role else PermissionSet()
        permissions[module] = {
            "view": current.view,
            "add": current.add,
            "edit": current.edit,
            "delete": current.delete,
        }

    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
        "full_name": user.full_name,
        "student_ids": user.student_ids,
        "branch_id": user.branch_id,
        "assigned_class_ids": user.assigned_class_ids,
        "role_name": role.name if role else user.role.replace("_", " ").title(),
        "permissions": permissions,
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
