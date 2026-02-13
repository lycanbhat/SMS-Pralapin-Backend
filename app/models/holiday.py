import datetime
from typing import Optional, List
from beanie import Document, Indexed
from pydantic import Field, BaseModel, ConfigDict

class Holiday(Document):
    """School holiday calendar model."""
    name: str
    date: Indexed(datetime.date)
    end_date: Optional[datetime.date] = None  # Optional for holiday ranges
    academic_year: Indexed(str)  # e.g., "2024-25"
    description: Optional[str] = None
    branch_id: Optional[str] = None  # null means applicable to all branches
    is_active: bool = True
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    class Settings:
        name = "holidays"
        use_state_management = True

class HolidayOut(BaseModel):
    id: str
    name: str
    date: datetime.date
    end_date: Optional[datetime.date] = None
    academic_year: str
    description: Optional[str] = None
    branch_id: Optional[str] = None
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

class HolidayCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    date: datetime.date
    end_date: Optional[datetime.date] = None
    academic_year: Optional[str] = None
    description: Optional[str] = None
    branch_id: Optional[str] = None

class HolidayUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Optional[str] = None
    date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None
    academic_year: Optional[str] = None
    description: Optional[str] = None
    branch_id: Optional[str] = None
    is_active: Optional[bool] = None
