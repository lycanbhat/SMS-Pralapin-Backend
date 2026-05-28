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
    branch = await Branch.get(PydanticObjectId(student.branch_id))
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    
    # Find class timings for the specific class
    class_timings = None
    for mapping in branch.class_fee_structures:
        if mapping.class_name == student.class_name or mapping.class_name == student.class_id:
            class_timings = {
                "start": mapping.start_time or "09:00",
                "end": mapping.end_time or "13:00"
            }
            break

    if not class_timings:
        # Fallback to general settings school hours if no class timings mapped
        class_timings = {
            "start": settings.school_hours_start,
            "end": settings.school_hours_end
        }

    from datetime import timezone, timedelta
    utc_now = datetime.now(timezone.utc)
    ist_now = utc_now + timedelta(hours=5, minutes=30)
    current_local_time = ist_now.time()

    start = _parse_time(class_timings["start"])
    end = _parse_time(class_timings["end"])
    if not (start <= current_local_time <= end):
        raise HTTPException(status_code=403, detail="Stream available only during class hours")

    config = next((c for c in branch.cctv_configs if c.stream_id == stream_id), None)
    if not config or not config.enabled:
        raise HTTPException(status_code=404, detail="Stream not found or disabled")
    signed_url = generate_signed_stream_url(config, student_id=student_id)
    return {"url": signed_url, "expires_in_seconds": 3600}
