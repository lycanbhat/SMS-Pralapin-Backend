from datetime import date, datetime
from typing import Optional
from beanie import Document, Indexed
from pydantic import Field, BaseModel

class AcademicYear(Document):
    """Academic year master records."""
    name: Indexed(str, unique=True)  # e.g., "2025-26"
    start_date: datetime
    end_date: datetime
    is_current: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "academic_years"
        use_state_management = True

class AcademicYearUpdate(BaseModel):
    is_current: Optional[bool] = None

class AcademicYearConfigUpdate(BaseModel):
    start_month: int
    start_day: int
    end_month: int
    end_day: int
