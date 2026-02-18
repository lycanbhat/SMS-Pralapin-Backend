"""Lesson plan API: day-wise plans per class."""
from datetime import date
from typing import Optional, List

from fastapi import APIRouter, HTTPException

from app.api.deps import TeacherOrAdmin
from app.models.lesson_plan import LessonPlan, LessonPlanCreate, LessonPlanUpdate


router = APIRouter()


@router.get("/")
async def list_lesson_plans(
    user: TeacherOrAdmin,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    branch_id: Optional[str] = None,
    class_id: Optional[str] = None,
) -> List[dict]:
    """List lesson plans, optionally filtered by date range / branch / class.

    Designed for the calendar UI – results are grouped client-side.
    """
    query = {}
    if from_date and to_date:
        query["date"] = {"$gte": from_date, "$lte": to_date}
    elif from_date:
        query["date"] = {"$gte": from_date}
    elif to_date:
        query["date"] = {"$lte": to_date}

    if branch_id:
        query["branch_id"] = branch_id
    if class_id:
        query["class_id"] = class_id

    plans = await LessonPlan.find(query).sort(LessonPlan.date).to_list()
    return [
        {
            "id": str(p.id),
            "branch_id": p.branch_id,
            "class_id": p.class_id,
            "date": p.date,
            "title": p.title,
            "description": p.description,
            "description_html": p.description_html,
        }
        for p in plans
    ]


@router.post("/", status_code=201)
async def create_lesson_plan(data: LessonPlanCreate, user: TeacherOrAdmin):
    """Create a new lesson plan."""
    plan = LessonPlan(
        branch_id=data.branch_id,
        class_id=data.class_id,
        date=data.date,
        title=data.title,
        description=data.description,
        description_html=data.description_html,
        created_by=str(user.id),
    )
    await plan.insert()
    return {"id": str(plan.id)}


@router.get("/{plan_id}")
async def get_lesson_plan(plan_id: str, user: TeacherOrAdmin):
    """Get a single lesson plan."""
    plan = await LessonPlan.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Lesson plan not found")
    return {
        "id": str(plan.id),
        "branch_id": plan.branch_id,
        "class_id": plan.class_id,
        "date": plan.date,
        "title": plan.title,
        "description": plan.description,
        "description_html": plan.description_html,
    }


@router.patch("/{plan_id}")
async def update_lesson_plan(plan_id: str, data: LessonPlanUpdate, user: TeacherOrAdmin):
    plan = await LessonPlan.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Lesson plan not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(plan, key, value)
    await plan.save()
    return {"id": str(plan.id)}


@router.delete("/{plan_id}", status_code=204)
async def delete_lesson_plan(plan_id: str, user: TeacherOrAdmin):
    plan = await LessonPlan.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Lesson plan not found")
    await plan.delete()
    return {}

