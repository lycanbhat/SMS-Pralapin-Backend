from datetime import date, datetime
from typing import Optional
from beanie import Document, Indexed
from pydantic import Field, BaseModel

class AttendanceStatus(BaseModel):
    student_id: str
    status: str  # present, absent

class AttendanceRecord(Document):
    """Attendance record for a class on a specific date."""
    branch_id: Indexed(str)
    class_id: Indexed(str)
    date: Indexed(date)
    marked_at: datetime = Field(default_factory=datetime.utcnow)
    marked_by: str  # user_id
    is_finalized: bool = False
    finalized_at: Optional[datetime] = None
    finalized_by: Optional[str] = None
    
    # We can store a summary or the actual list here if we want class-level view
    # But for now, the source of truth for student status is in Student.attendance_logs
    # or we can store it here too for faster class-wise retrieval.
    # Let's store it here for the "Attendance Management" module's specific needs.
    attendance: list[AttendanceStatus] = Field(default_factory=list)

    class Settings:
        name = "attendance_records"
        use_state_management = True
