from fastapi import APIRouter, Depends
from datetime import date, datetime, timedelta
from typing import Dict, Any

from app.api.deps import AdminOnly
from app.models.student import Student
from app.models.user import User, UserRole
from app.models.branch import Branch
from app.models.attendance import AttendanceRecord
from app.models.billing import Billing, PaymentStatus
from app.models.feed import FeedPost
from app.models.holiday import Holiday

router = APIRouter()

@router.get("/stats")
async def get_admin_stats(admin: AdminOnly) -> Dict[str, Any]:
    """Get overview statistics for the admin dashboard."""
    
    # Basic counts
    total_students = await Student.count()
    total_staff = await User.find(User.role != UserRole.PARENT).count()
    total_branches = await Branch.count()
    
    # Attendance for today
    today = date.today()
    attendance_records = await AttendanceRecord.find(AttendanceRecord.date == today).to_list()
    
    total_present = 0
    total_absent = 0
    classes_marked = len(attendance_records)
    
    for record in attendance_records:
        for item in record.attendance:
            if item.status == "present":
                total_present += 1
            elif item.status == "absent":
                total_absent += 1
    
    # Billing summary
    billings = await Billing.find_all().to_list()
    total_expected = sum(b.fee_structure.amount for b in billings)
    total_received = sum(b.amount_paid for b in billings)
    pending_amount = total_expected - total_received
    
    # Recent announcements (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_announcements = await FeedPost.find(FeedPost.created_at >= thirty_days_ago).count()
    
    # Upcoming holidays
    upcoming_holidays = await Holiday.find(Holiday.date >= today, Holiday.is_active == True).sort("date").limit(5).to_list()
    
    return {
        "counts": {
            "students": total_students,
            "staff": total_staff,
            "branches": total_branches,
            "announcements": recent_announcements,
        },
        "attendance": {
            "present": total_present,
            "absent": total_absent,
            "classes_marked": classes_marked,
            "date": today.isoformat(),
        },
        "finance": {
            "total_expected": total_expected,
            "total_received": total_received,
            "pending_amount": pending_amount,
        },
        "upcoming_holidays": [
            {
                "name": h.name,
                "date": h.date.isoformat(),
                "days": (h.end_date - h.date).days + 1 if h.end_date else 1
            }
            for h in upcoming_holidays
        ]
    }
