from datetime import datetime
from typing import Optional
from beanie import Document, Indexed
from pydantic import Field

class SchoolClass(Document):
    """School class model (e.g., Nursery, Class 1, etc.)"""
    name: Indexed(str)
    branch_id: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "classes"
        use_state_management = True
