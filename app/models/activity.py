"""Daily logs, lesson progress, photo metadata."""
from datetime import datetime
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field


class PhotoMetadata(BaseModel):
    s3_key: str
    url: str
    caption: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class Activity(Document):
    """Activity document: daily logs, lessons, photos."""

    student_id: Indexed(str)
    date: str  # YYYY-MM-DD
    lesson_progress: Optional[str] = None
    notes: Optional[str] = None
    photos: list[PhotoMetadata] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None  # user_id

    class Settings:
        name = "activities"
        use_state_management = True


class ActivityCreate(BaseModel):
    student_id: str
    date: str
    lesson_progress: Optional[str] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None
