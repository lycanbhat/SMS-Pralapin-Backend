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


async def init_db():
    client = AsyncIOMotorClient(settings.mongodb_url)
    await init_beanie(
        database=client[settings.mongodb_db_name],
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
