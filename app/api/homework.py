"""Homework API: daily homework per class."""
from datetime import date
from typing import Optional, List

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.api.deps import TeacherOrAdmin
from app.models.homework import Homework, HomeworkCreate, HomeworkUpdate
from app.services.s3 import upload_homework_attachment_to_s3
from app.models.student import Student
from app.models.user import User, UserRole
from app.services.fcm import send_homework_notification


router = APIRouter()

ALLOWED_ATTACHMENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}
ALLOWED_ATTACHMENT_EXTS = {"pdf", "jpeg", "jpg", "png"}


@router.post("/upload-attachment")
async def upload_homework_attachment(file: UploadFile = File(...), user: TeacherOrAdmin = ...):
    """Upload homework attachment (PDF, JPEG, JPG, PNG). Returns url and filename."""
    ext = (file.filename or "").split(".")[-1].lower()
    if ext not in ALLOWED_ATTACHMENT_EXTS:
        raise HTTPException(
            status_code=400,
            detail="File must be PDF, JPEG, JPG, or PNG",
        )
    if file.content_type and file.content_type not in ALLOWED_ATTACHMENT_TYPES:
        if ext in ALLOWED_ATTACHMENT_EXTS:
            pass  # Allow by extension if content-type is wrong
        else:
            raise HTTPException(
                status_code=400,
                detail="File must be PDF, JPEG, JPG, or PNG",
            )
    url, _ = await upload_homework_attachment_to_s3(file)
    return {"url": url, "filename": file.filename or f"attachment.{ext}"}


@router.get("/")
async def list_homework(
    user: TeacherOrAdmin,
    for_date: Optional[date] = None,
    branch_id: Optional[str] = None,
    class_id: Optional[str] = None,
) -> List[dict]:
    """List homework entries."""
    query: dict = {}
    if for_date:
        query["date"] = for_date
    if branch_id:
        query["branch_id"] = branch_id
    if class_id:
        query["class_id"] = class_id

    # Show latest homework first (most recently created at the top)
    items = await Homework.find(query).sort(-Homework.created_at).to_list()
    return [
        {
            "id": str(h.id),
            "branch_id": h.branch_id,
            "class_id": h.class_id,
            "date": h.date,
            "submission_date": h.submission_date,
            "title": h.title,
            "description": h.description,
            "description_html": h.description_html,
            "attachment_url": h.attachment_url,
            "attachment_filename": h.attachment_filename,
        }
        for h in items
    ]


@router.post("/", status_code=201)
async def create_homework(data: HomeworkCreate, user: TeacherOrAdmin):
    """Create homework for a class and notify parents."""
    hw = Homework(
        branch_id=data.branch_id,
        class_id=data.class_id,
        date=data.date,
        submission_date=data.submission_date,
        title=data.title,
        description=data.description,
        description_html=data.description_html,
        attachment_url=data.attachment_url,
        attachment_filename=data.attachment_filename,
        created_by=str(user.id),
    )
    await hw.insert()

    # Notify parents asynchronously (fire and forget)
    await send_homework_notification(hw)

    return {"id": str(hw.id)}


@router.get("/{homework_id}")
async def get_homework(homework_id: str, user: TeacherOrAdmin):
    """Get a single homework entry."""
    hw = await Homework.get(homework_id)
    if not hw:
        raise HTTPException(status_code=404, detail="Homework not found")
    return {
        "id": str(hw.id),
        "branch_id": hw.branch_id,
        "class_id": hw.class_id,
        "date": hw.date,
        "submission_date": hw.submission_date,
        "title": hw.title,
        "description": hw.description,
        "description_html": hw.description_html,
        "attachment_url": hw.attachment_url,
        "attachment_filename": hw.attachment_filename,
    }


@router.patch("/{homework_id}")
async def update_homework(homework_id: str, data: HomeworkUpdate, user: TeacherOrAdmin):
    hw = await Homework.get(homework_id)
    if not hw:
        raise HTTPException(status_code=404, detail="Homework not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(hw, key, value)
    await hw.save()
    return {"id": str(hw.id)}


@router.delete("/{homework_id}", status_code=204)
async def delete_homework(homework_id: str, user: TeacherOrAdmin):
    hw = await Homework.get(homework_id)
    if not hw:
        raise HTTPException(status_code=404, detail="Homework not found")
    await hw.delete()
    return {}

