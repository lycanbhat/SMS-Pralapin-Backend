from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from beanie import PydanticObjectId
from pydantic import BaseModel
import pandas as pd
import io

from app.api.deps import TeacherOrAdmin, AdminOnly, require_roles
from app.models.student import Student, AttendanceLog
from app.models.branch import Branch
from app.models.attendance import AttendanceRecord, AttendanceStatus
from app.models.user import UserRole
from app.services.fcm import send_attendance_notification

router = APIRouter()

@router.get("/classes")
async def get_classes(user: TeacherOrAdmin):
    """Fetch classes assigned to a teacher/faculty, or all in branch for coordinator, or all for admin."""
    all_branches = await Branch.find(Branch.is_active == True).to_list()
    classes = []
    for b in all_branches:
        branch_id_str = str(b.id)
        # Check branch-level permission
        is_admin = user.role == UserRole.ADMIN
        
        if not is_admin:
            if user.role == UserRole.COORDINATOR:
                if branch_id_str != user.branch_id:
                    continue
            else:
                # Faculty / Teacher
                if branch_id_str != user.branch_id:
                    continue

        for cls_name in b.classes:
            # For Faculty, only show assigned classes
            if not is_admin and user.role != UserRole.COORDINATOR:
                if cls_name not in user.assigned_class_ids:
                    continue

            classes.append(
                {
                    "id": cls_name,  # Using name as ID
                    "name": cls_name,
                    "branch_id": branch_id_str,
                    "branch_name": b.name,
                }
            )
    return classes


@router.get("/students/{branch_id}/{class_id}")
async def get_students_for_class(branch_id: str, class_id: str, user: TeacherOrAdmin):
    """Fetch students for a specific class in a branch."""
    # Security check
    if user.role == UserRole.ADMIN:
        pass
    elif user.role == UserRole.COORDINATOR:
        if branch_id != user.branch_id:
            raise HTTPException(
                status_code=403, detail="This branch is not your assigned branch"
            )
    else:
        # Faculty / Teacher
        if branch_id != user.branch_id:
            raise HTTPException(status_code=403, detail="Branch mismatch")
        if class_id not in user.assigned_class_ids:
            raise HTTPException(
                status_code=403, detail="You are not assigned to this class"
            )

    students = (
        await Student.find(
            {"branch_id": branch_id, "class_id": class_id, "is_active": True}
        )
        .sort("roll_number")
        .to_list()
    )
    return [
        {
            "id": str(s.id),
            "full_name": s.full_name,
            "roll_number": s.roll_number,
            "class_id": s.class_id,
        }
        for s in students
    ]


@router.get("/record/{branch_id}/{class_id}/{date_str}")
async def get_attendance_record(
    branch_id: str, class_id: str, date_str: str, user: TeacherOrAdmin
):
    """Fetch attendance record for a class and date."""
    # Security check
    if user.role == UserRole.ADMIN:
        pass
    elif user.role == UserRole.COORDINATOR:
        if branch_id != user.branch_id:
            raise HTTPException(status_code=403, detail="Branch mismatch")
    else:
        if branch_id != user.branch_id or class_id not in user.assigned_class_ids:
            raise HTTPException(
                status_code=403, detail="You are not authorized for this class"
            )

    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format (YYYY-MM-DD)")

    record = await AttendanceRecord.find_one(
        {"branch_id": branch_id, "class_id": class_id, "date": d}
    )
    if not record:
        return {
            "branch_id": branch_id,
            "class_id": class_id,
            "date": date_str,
            "is_finalized": False,
            "attendance": [],
        }

    return record


class AttendanceBulkMarkRequest(BaseModel):
    branch_id: str
    class_id: str
    date_str: str
    attendance: List[AttendanceStatus]


@router.post("/mark-bulk")
async def mark_attendance_bulk(
    data: AttendanceBulkMarkRequest,
    user: TeacherOrAdmin,
):
    """Mark attendance for multiple students in a class-date."""
    branch_id = data.branch_id
    class_id = data.class_id
    date_str = data.date_str
    attendance = data.attendance

    # Security check
    if user.role == UserRole.ADMIN:
        pass
    elif user.role == UserRole.COORDINATOR:
        if branch_id != user.branch_id:
            raise HTTPException(status_code=403, detail="Branch mismatch")
    else:
        if branch_id != user.branch_id or class_id not in user.assigned_class_ids:
            raise HTTPException(
                status_code=403, detail="You are not authorized for this class"
            )

    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format (YYYY-MM-DD)")

    # Check if finalized
    record = await AttendanceRecord.find_one(
        {"branch_id": branch_id, "class_id": class_id, "date": d}
    )
    if record and record.is_finalized:
        raise HTTPException(
            status_code=400,
            detail="Attendance for this date is already finalized and locked",
        )

    if not record:
        record = AttendanceRecord(
            branch_id=branch_id,
            class_id=class_id,
            date=d,
            marked_by=str(user.id),
            attendance=attendance,
        )
    else:
        record.attendance = attendance
        record.marked_by = str(user.id)
        record.marked_at = datetime.utcnow()

    await record.save()

    # Also update individual student logs for history/parent view
    for att in attendance:
        try:
            s_id = PydanticObjectId(att.student_id)
        except Exception:
            continue

        student = await Student.get(s_id)
        if student:
            log = AttendanceLog(
                date=d,
                status=att.status,
                marked_at=datetime.utcnow(),
                marked_by=str(user.id),
            )
            # Dedupe by date
            student.attendance_logs = [l for l in student.attendance_logs if l.date != d]
            student.attendance_logs.append(log)
            await student.save()

            # Optional: Notify parents if status is absent
            if att.status == "absent":
                await send_attendance_notification(student, log)

    return {
        "status": "success",
        "message": f"Attendance marked for {len(attendance)} students",
    }


@router.post("/finalize/{branch_id}/{class_id}/{date_str}")
async def finalize_attendance(
    branch_id: str, class_id: str, date_str: str, user: TeacherOrAdmin
):
    """Finalize/lock attendance for a date."""
    # Security check
    if user.role == UserRole.ADMIN:
        pass
    elif user.role == UserRole.COORDINATOR:
        if branch_id != user.branch_id:
            raise HTTPException(status_code=403, detail="Branch mismatch")
    else:
        if branch_id != user.branch_id or class_id not in user.assigned_class_ids:
            raise HTTPException(
                status_code=403, detail="You are not authorized for this class"
            )

    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format (YYYY-MM-DD)")

    record = await AttendanceRecord.find_one(
        {"branch_id": branch_id, "class_id": class_id, "date": d}
    )
    if not record:
        raise HTTPException(
            status_code=404, detail="Attendance record not found for this date"
        )

    record.is_finalized = True
    record.finalized_at = datetime.utcnow()
    record.finalized_by = str(user.id)
    await record.save()

    return {"status": "success", "message": "Attendance finalized and locked"}


@router.get("/report")
async def download_attendance_report(
    branch_id: str,
    class_id: str,
    from_date: str,
    to_date: str,
    user: AdminOnly,
    format: str = Query("csv", enum=["csv", "excel"]),
):
    """Download attendance report for a class and date range."""
    try:
        d_from = date.fromisoformat(from_date)
        d_to = date.fromisoformat(to_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format (YYYY-MM-DD)")

    # Fetch records
    records = await AttendanceRecord.find(
        {
            "branch_id": branch_id,
            "class_id": class_id,
            "date": {"$gte": d_from, "$lte": d_to},
        }
    ).to_list()

    # Fetch students to get names
    students = await Student.find({"branch_id": branch_id, "class_id": class_id}).to_list()
    student_map = {str(s.id): s.full_name for s in students}
    student_roll_map = {str(s.id): s.roll_number for s in students}

    data = []
    for record in records:
        for att in record.attendance:
            data.append(
                {
                    "Date": record.date,
                    "Student ID": att.student_id,
                    "Roll Number": student_roll_map.get(att.student_id, ""),
                    "Student Name": student_map.get(att.student_id, "Unknown"),
                    "Status": att.status,
                }
            )

    if not data:
        raise HTTPException(
            status_code=404, detail="No records found for the given criteria"
        )

    df = pd.DataFrame(data)

    if format == "csv":
        stream = io.StringIO()
        df.to_csv(stream, index=False)
        return StreamingResponse(
            iter([stream.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=attendance_{branch_id}_{class_id}_{from_date}_{to_date}.csv"
            },
        )
    else:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Attendance")
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=attendance_{branch_id}_{class_id}_{from_date}_{to_date}.xlsx"
            },
        )
