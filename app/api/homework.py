"""Homework API: daily homework per class."""
from datetime import date
from typing import Optional, List

from fastapi import APIRouter, HTTPException

from app.api.deps import TeacherOrAdmin
from app.models.homework import Homework, HomeworkCreate, HomeworkUpdate
from app.models.student import Student
from app.models.user import User, UserRole
from app.services.fcm import send_homework_notification


router = APIRouter()


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

    items = await Homework.find(query).sort(Homework.date).to_list()
    return [
        {
            "id": str(h.id),
            "branch_id": h.branch_id,
            "class_id": h.class_id,
            "date": h.date,
            "title": h.title,
            "description": h.description,
            "description_html": h.description_html,
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
        title=data.title,
        description=data.description,
        description_html=data.description_html,
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
        "title": hw.title,
        "description": hw.description,
        "description_html": hw.description_html,
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

