"""Pralapin SMS - FastAPI entrypoint."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import ServerSelectionTimeoutError

from app.config import settings
from app.db import init_db
from app.seed import seed_admin
from app.services.academic_year import ensure_academic_year
from app.api import auth, users, students, activities, billing, branches, settings as settings_api, feed, cctv, attendance, mobile, staff, holidays, dashboard, gallery

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
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
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(students.router, prefix="/api/students", tags=["Students"])
app.include_router(activities.router, prefix="/api/activities", tags=["Activities"])
app.include_router(billing.router, prefix="/api/billing", tags=["Billing"])
app.include_router(branches.router, prefix="/api/branches", tags=["Branches"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["Settings"])
app.include_router(feed.router, prefix="/api/feed", tags=["Feed / Announcements"])
app.include_router(cctv.router, prefix="/api/cctv", tags=["CCTV / Live Stream"])
app.include_router(attendance.router, prefix="/api/attendance", tags=["Attendance"])
app.include_router(mobile.router, prefix="/api/mobile", tags=["Mobile App"])
app.include_router(staff.router, prefix="/api/staff", tags=["Staff Management"])
app.include_router(holidays.router, prefix="/api/holidays", tags=["Holidays"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(gallery.router, prefix="/api/gallery", tags=["Gallery"])


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}
