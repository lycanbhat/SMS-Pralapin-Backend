"""MongoDB connection and Beanie document registration."""
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.models import (
    User,
    Student,
    Activity,
    Billing,
    Branch,
    AppSettings,
    FeedPost,
    SchoolClass,
    AttendanceRecord,
    Holiday,
    AcademicYear,
    Album,
    Role,
)


_client = None


async def db_startup():
    """Connect to MongoDB and initialize Beanie ODM."""
    global _client
    _client = AsyncIOMotorClient(settings.mongodb_url)
    await init_beanie(
        database=_client[settings.mongodb_db_name],
        document_models=[
            User,
            Student,
            Activity,
            Billing,
            Branch,
            AppSettings,
            FeedPost,
            SchoolClass,
            AttendanceRecord,
            Holiday,
            AcademicYear,
            Album,
            Role,
        ],
    )


async def db_shutdown():
    """Close MongoDB connection."""
    global _client
    if _client:
        _client.close()
        _client = None


async def init_db():
    """Alias for db_startup (backward compatibility)."""
    await db_startup()
