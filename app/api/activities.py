"""Activities: daily logs, lesson progress, photo metadata (S3 URLs)."""
from fastapi import APIRouter, HTTPException, UploadFile, File
from beanie import PydanticObjectId

from app.api.deps import CurrentUser, TeacherOrAdmin
from app.models.user import UserRole
from app.models.student import Student
from app.models.activity import Activity, ActivityCreate, PhotoMetadata
from app.services.s3 import upload_photo_to_s3

router = APIRouter()


@router.get("/")
async def list_activities(student_id: str, user: CurrentUser):
    student = await Student.get(PydanticObjectId(student_id))
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if user.role == UserRole.PARENT and str(student.id) not in user.student_ids:
        raise HTTPException(status_code=403, detail="Not authorized")
    activities = await Activity.find(Activity.student_id == student_id).sort(-Activity.date).to_list()
    return [
        {
            "id": str(a.id),
            "date": a.date,
            "lesson_progress": a.lesson_progress,
            "notes": a.notes,
            "photos": a.photos,
        }
        for a in activities
    ]


@router.post("/", status_code=201)
async def create_activity(data: ActivityCreate, user: TeacherOrAdmin):
    act = Activity(
        student_id=data.student_id,
        date=data.date,
        lesson_progress=data.lesson_progress,
        notes=data.notes,
        created_by=str(user.id),
    )
    await act.insert()
    return {"id": str(act.id), "date": act.date}


@router.post("/{activity_id}/photos")
async def add_photo(
    activity_id: str,
    user: TeacherOrAdmin,
    file: UploadFile = File(...),
    caption: str | None = None,
):
    act = await Activity.get(PydanticObjectId(activity_id))
    if not act:
        raise HTTPException(status_code=404, detail="Activity not found")
    url, s3_key = await upload_photo_to_s3(file, student_id=act.student_id, activity_id=activity_id)
    meta = PhotoMetadata(s3_key=s3_key, url=url, caption=caption)
    act.photos.append(meta)
    await act.save()
    return {"url": url, "caption": caption}
