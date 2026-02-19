"""Homework: daily homework per class."""
from datetime import datetime, date
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field


class Homework(Document):
    """Homework assigned to a class on a specific date."""

    branch_id: Indexed(str)
    class_id: str
    date: date  # Created/assigned date
    submission_date: Optional[date] = None  # Due date

    title: str
    description: Optional[str] = None
    description_html: Optional[str] = None
    attachment_url: Optional[str] = None  # PDF or image attachment
    attachment_filename: Optional[str] = None

    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "homework"
        use_state_management = True


class HomeworkCreate(BaseModel):
    branch_id: str
    class_id: str
    date: date
    submission_date: Optional[date] = None
    title: str
    description: Optional[str] = None
    description_html: Optional[str] = None
    attachment_url: Optional[str] = None
    attachment_filename: Optional[str] = None


class HomeworkUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    description_html: Optional[str] = None
    submission_date: Optional[date] = None
    attachment_url: Optional[str] = None
    attachment_filename: Optional[str] = None

