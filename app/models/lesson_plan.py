"""Lesson plans: day-wise plans per class."""
from datetime import datetime, date
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field


class LessonPlan(Document):
    """Lesson plan for a class on a specific day."""

    branch_id: Indexed(str)
    class_id: str  # same identifier used in attendance.classes
    date: date

    title: str
    description: Optional[str] = None  # plain text summary
    description_html: Optional[str] = None  # RTE content

    created_by: str  # user id
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "lesson_plans"
        use_state_management = True


class LessonPlanCreate(BaseModel):
    branch_id: str
    class_id: str
    date: date
    title: str
    description: Optional[str] = None
    description_html: Optional[str] = None


class LessonPlanUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    description_html: Optional[str] = None

