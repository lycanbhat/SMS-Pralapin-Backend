"""Entrypoint: FastAPI with module-level imports."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db import db_startup, db_shutdown


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start-up
    await db_startup()
    await ensure_default_roles()
    yield
    # Shutdown
    await db_shutdown()


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url="/api/docs" if settings.debug else None,  # swagger hidden in prod
)


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API routes
from app.api import auth, users, students, activities, billing, branches, settings as settings_api, feed, cctv, attendance, mobile, staff, holidays, dashboard, gallery, roles
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(students.router, prefix="/api/students", tags=["Students"])
app.include_router(activities.router, prefix="/api/activities", tags=["Activities"])
app.include_router(billing.router, prefix="/api/billing", tags=["Billing"])
app.include_router(branches.router, prefix="/api/branches", tags=["Branches"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["Settings"])
app.include_router(roles.router, prefix="/api/roles", tags=["Roles"])
app.include_router(feed.router, prefix="/api/feed", tags=["Feed"])
app.include_router(cctv.router, prefix="/api/cctv", tags=["CCTV"])
app.include_router(attendance.router, prefix="/api/attendance", tags=["Attendance"])
app.include_router(mobile.router, prefix="/api/mobile", tags=["Mobile"])
app.include_router(staff.router, prefix="/api/staff", tags=["Staff"])
app.include_router(holidays.router, prefix="/api/holidays", tags=["Holidays"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(gallery.router, prefix="/api/gallery", tags=["Gallery"])


from app.services.roles import ensure_default_roles
from fastapi.staticfiles import StaticFiles
import os

# Static files from /backend/static
static_dir = os.path.join(os.path.dirname(__file__), "..")
if os.path.isdir(os.path.join(static_dir, "static")):
    app.mount("/static", StaticFiles(directory=os.path.join(static_dir, "static")), name="static")


# Custom exception handler for validation errors
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )