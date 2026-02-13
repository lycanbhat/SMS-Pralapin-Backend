"""CCTV: token-gated signed URL (school hours only, parent student_id validated)."""
from datetime import datetime, time
from fastapi import APIRouter, HTTPException
from beanie import PydanticObjectId

from app.api.deps import ParentOnly
from app.config import settings
from app.models.student import Student
from app.models.branch import Branch
from app.services.cctv import generate_signed_stream_url

router = APIRouter()


def _parse_time(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


@router.get("/stream-url")
async def get_stream_url(student_id: str, stream_id: str, user: ParentOnly):
    """Validate parent's student_id and school hours; return signed HLS URL."""
    student = await Student.get(PydanticObjectId(student_id))
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if str(student.id) not in user.student_ids:
        raise HTTPException(status_code=403, detail="Not authorized for this student")
    now = datetime.utcnow().time()
    start = _parse_time(settings.school_hours_start)
    end = _parse_time(settings.school_hours_end)
    if not (start <= now <= end):
        raise HTTPException(status_code=403, detail="Stream available only during school hours")
    branch = await Branch.get(PydanticObjectId(student.branch_id))
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    config = next((c for c in branch.cctv_configs if c.stream_id == stream_id), None)
    if not config or not config.enabled:
        raise HTTPException(status_code=404, detail="Stream not found or disabled")
    signed_url = generate_signed_stream_url(config, student_id=student_id)
    return {"url": signed_url, "expires_in_seconds": 3600}
