"""Mobile parent app endpoints: dashboard and profile payloads."""
from datetime import date, timedelta

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, ParentOnly
from app.models.branch import Branch
from app.models.feed import FeedPost
from app.models.settings import AppSettings
from app.models.student import Student
from app.models.user import User
from app.services.announcements import (
    build_author_name_map,
    build_branch_name_map,
    is_announcement_visible,
    list_announcements_for_scope,
    parent_branch_ids,
    safe_object_id,
    serialize_announcement,
    sort_announcements,
)

router = APIRouter()


def _safe_oid(value: str | None) -> PydanticObjectId | None:
    return safe_object_id(value)


async def _linked_students(user: User) -> list[Student]:
    object_ids: list[PydanticObjectId] = []
    for student_id in user.student_ids:
        oid = _safe_oid(student_id)
        if oid:
            object_ids.append(oid)
    if not object_ids:
        return []
    students = await Student.find(
        {
            "_id": {"$in": object_ids},
            "is_active": True,
        }
    ).to_list()
    return sorted(students, key=lambda s: s.full_name.lower())


def _attendance_status_for_date(student: Student, for_date: date) -> str:
    for log in student.attendance_logs:
        if log.date == for_date:
            return log.status
    return "unknown"


@router.get("/dashboard")
async def dashboard(user: CurrentUser, student_id: str | None = None):
    students = await _linked_students(user)
    if not students:
        return {
            "parent": {
                "id": str(user.id),
                "full_name": user.full_name,
                "email": user.email,
            },
            "student": None,
            "attendance_last_5_days": [],
            "latest_announcement": None,
            "latest_news": None,
            "quick_links": [
                {"title": "Attendance", "route": "/attendance"},
                {"title": "Announcements", "route": "/feed"},
                {"title": "Photo Gallery", "route": "/gallery"},
                {"title": "Fee Activity", "route": "/fees"},
                {"title": "Watch Live", "route": "/watch-live"},
                {"title": "Calendar", "route": "/calendar"},
            ],
        }

    selected_student = students[0]
    if student_id:
        selected_student = next((s for s in students if str(s.id) == student_id), selected_student)

    today = date.today()
    attendance_last_6_days = []
    for days_ago in range(5, -1, -1):
        current_day = today - timedelta(days=days_ago)
        attendance_last_6_days.append(
            {
                "date": current_day.isoformat(),
                "day": current_day.strftime("%a"),
                "status": _attendance_status_for_date(selected_student, current_day),
            }
        )

    posts = await list_announcements_for_scope({selected_student.branch_id})
    posts = sort_announcements(posts)
    posts = posts[:20]
    latest_announcement = posts[0] if posts else None
    latest_news = posts[1] if len(posts) > 1 else None

    latest_posts = [p for p in [latest_announcement, latest_news] if p]
    author_name_map = await build_author_name_map(latest_posts)
    branch_name_map = await build_branch_name_map(latest_posts)
    latest_announcement_payload = (
        serialize_announcement(latest_announcement, author_name_map, branch_name_map)
        if latest_announcement
        else None
    )
    latest_news_payload = (
        serialize_announcement(latest_news, author_name_map, branch_name_map)
        if latest_news
        else None
    )

    branch_name = None
    class_timings = None
    branch_oid = _safe_oid(selected_student.branch_id)
    if branch_oid:
        branch = await Branch.get(branch_oid)
        if branch:
            branch_name = branch.name
            # Find timings for the specific class
            for mapping in branch.class_fee_structures:
                if mapping.class_name == selected_student.class_name:
                    class_timings = {
                        "start": mapping.start_time or "09:00",
                        "end": mapping.end_time or "13:00"
                    }
                    break

    settings = await AppSettings.find_one()
    cctv_enabled = settings.cctv_enabled if settings else True

    return {
        "parent": {
            "id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
        },
        "student": {
            "id": str(selected_student.id),
            "full_name": selected_student.full_name,
            "admission_number": selected_student.admission_number,
            "class_name": selected_student.class_name,
            "branch_name": branch_name,
            "class_timings": class_timings,
        },
        "cctv_enabled": cctv_enabled,
        "attendance_last_6_days": attendance_last_6_days,
        "latest_announcement": latest_announcement_payload,
        "latest_news": latest_news_payload,
        "quick_links": [
            {"title": "Announcements", "route": "/feed"},
            {"title": "Photo Gallery", "route": "/gallery"},
            {"title": "Fee Activity", "route": "/fees"},
            {"title": "Watch Live", "route": "/watch-live"},
            {"title": "Calendar", "route": "/calendar"},
            {"title": "Homework", "route": "/homework"},
        ],
    }


@router.get("/profile")
async def profile(user: CurrentUser):
    students = await _linked_students(user)

    branch_cache: dict[str, Branch | None] = {}
    children = []
    for s in students:
        branch_name = None
        branch_address = None
        branch_id = s.branch_id
        if branch_id not in branch_cache:
            branch = None
            branch_oid = _safe_oid(branch_id)
            if branch_oid:
                branch = await Branch.get(branch_oid)
            branch_cache[branch_id] = branch
        branch_obj = branch_cache.get(branch_id)
        if branch_obj:
            branch_name = branch_obj.name
            branch_address = branch_obj.address

        children.append(
            {
                "id": str(s.id),
                "full_name": s.full_name,
                "admission_number": s.admission_number,
                "class_name": s.class_name,
                "roll_number": s.roll_number,
                "academic_year": s.academic_year,
                "branch_name": branch_name,
                "branch_address": branch_address,
                "date_of_birth": s.date_of_birth.isoformat() if s.date_of_birth else None,
                "gender": s.gender,
            }
        )

    return {
        "parent": {
            "id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "role": user.role.value,
        },
        "children": children,
    }


@router.get("/attendance")
async def student_attendance(
    user: ParentOnly,
    student_id: str | None = None,
    month: int | None = None,
    year: int | None = None,
):
    students = await _linked_students(user)
    if not students:
        return {"items": []}

    selected_student = students[0]
    if student_id:
        selected_student = next(
            (s for s in students if str(s.id) == student_id), selected_student
        )

    logs = selected_student.attendance_logs
    if month and year:
        logs = [log for log in logs if log.date.month == month and log.date.year == year]

    # Sort logs by date descending
    logs.sort(key=lambda x: x.date, reverse=True)

    return {
        "student_id": str(selected_student.id),
        "student_name": selected_student.full_name,
        "items": [
            {
                "date": log.date.isoformat(),
                "status": log.status,
                "marked_at": log.marked_at.isoformat(),
            }
            for log in logs
        ],
    }


@router.get("/announcements")
async def list_mobile_announcements(
    user: ParentOnly,
    student_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    students = await _linked_students(user)
    selected_students = students
    if student_id:
        selected_students = [s for s in students if str(s.id) == student_id]
        if not selected_students:
            raise HTTPException(status_code=403, detail="Not authorized for this student")

    branch_scope = {s.branch_id for s in selected_students if s.branch_id}
    posts = await list_announcements_for_scope(branch_scope)
    posts = sort_announcements(posts)
    total = len(posts)
    page = posts[offset : offset + limit]

    author_name_map = await build_author_name_map(page)
    branch_name_map = await build_branch_name_map(page)
    items = [serialize_announcement(p, author_name_map, branch_name_map) for p in page]

    return {
        "items": items,
        "limit": limit,
        "offset": offset,
        "total": total,
        "student_id": student_id,
    }


@router.get("/announcements/{announcement_id}")
async def get_mobile_announcement(announcement_id: str, user: ParentOnly):
    oid = safe_object_id(announcement_id)
    if not oid:
        raise HTTPException(status_code=400, detail="Invalid announcement_id")

    post = await FeedPost.get(oid)
    if not post:
        raise HTTPException(status_code=404, detail="Announcement not found")

    allowed_branch_ids = set(await parent_branch_ids(user))
    if not is_announcement_visible(post, allowed_branch_ids):
        raise HTTPException(status_code=403, detail="Not authorized for this announcement")

    author_name_map = await build_author_name_map([post])
    branch_name_map = await build_branch_name_map([post])
    return serialize_announcement(post, author_name_map, branch_name_map)
