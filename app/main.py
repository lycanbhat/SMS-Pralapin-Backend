"""Pralapin SMS - FastAPI entrypoint."""
import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pymongo.errors import ServerSelectionTimeoutError

from app.config import settings
from app.db import init_db
from app.seed import seed_admin
from app.services.academic_year import ensure_academic_year
from app.services.roles import ensure_default_roles
from app.api import auth, users, students, activities, billing, branches, settings as settings_api, feed, cctv, attendance, mobile, staff, holidays, dashboard, gallery, roles
from app.api.deps import require_module_permission

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        await ensure_default_roles()
        await seed_admin()
        await ensure_academic_year()
    except ServerSelectionTimeoutError as e:
        logger.error(
            "MongoDB is not running. Start it with: docker compose up -d (from project root)"
        )
        raise RuntimeError(
            "MongoDB connection failed. Start MongoDB (e.g. docker compose up -d)."
        ) from e
    yield
    # shutdown if needed


app = FastAPI(
    title=settings.app_name,
    description="Central hub: MongoDB persistence, React admin, Flutter parent app",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(users.router, prefix="/api/users", tags=["Users"], dependencies=[Depends(require_module_permission("users"))])
app.include_router(students.router, prefix="/api/students", tags=["Students"], dependencies=[Depends(require_module_permission("students"))])
app.include_router(activities.router, prefix="/api/activities", tags=["Activities"], dependencies=[Depends(require_module_permission("activities"))])
app.include_router(billing.router, prefix="/api/billing", tags=["Billing"], dependencies=[Depends(require_module_permission("billing"))])
app.include_router(branches.router, prefix="/api/branches", tags=["Branches"], dependencies=[Depends(require_module_permission("branches"))])
app.include_router(settings_api.router, prefix="/api/settings", tags=["Settings"], dependencies=[Depends(require_module_permission("settings"))])
app.include_router(feed.router, prefix="/api/feed", tags=["Feed / Announcements"], dependencies=[Depends(require_module_permission("feed"))])
app.include_router(cctv.router, prefix="/api/cctv", tags=["CCTV / Live Stream"], dependencies=[Depends(require_module_permission("cctv"))])
app.include_router(attendance.router, prefix="/api/attendance", tags=["Attendance"], dependencies=[Depends(require_module_permission("attendance"))])
app.include_router(mobile.router, prefix="/api/mobile", tags=["Mobile App"], dependencies=[Depends(require_module_permission("mobile"))])
app.include_router(staff.router, prefix="/api/staff", tags=["Staff Management"], dependencies=[Depends(require_module_permission("staff"))])
app.include_router(holidays.router, prefix="/api/holidays", tags=["Holidays"], dependencies=[Depends(require_module_permission("holidays"))])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"], dependencies=[Depends(require_module_permission("dashboard"))])
app.include_router(gallery.router, prefix="/api/gallery", tags=["Gallery"], dependencies=[Depends(require_module_permission("gallery"))])
app.include_router(roles.router, prefix="/api/roles", tags=["Roles & Permissions"], dependencies=[Depends(require_module_permission("roles_permissions"))])


# Serve static files (logos, etc.)
_static_dir = Path(__file__).resolve().parent.parent / "static"
if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}
