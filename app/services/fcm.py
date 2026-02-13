"""Firebase Cloud Messaging: feed announcements and attendance notifications."""
import firebase_admin
from firebase_admin import credentials, messaging
from typing import Optional, List
import logging

from app.models.feed import FeedPost
from app.models.student import Student, AttendanceLog
from app.models.user import User, UserRole
from app.config import settings

logger = logging.getLogger(__name__)

_firebase_app = None

def _get_firebase_app():
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app
    
    if not settings.firebase_credentials_path:
        logger.warning("FIREBASE_CREDENTIALS_PATH not set. FCM will be disabled.")
        return None
    
    try:
        cred = credentials.Certificate(settings.firebase_credentials_path)
        _firebase_app = firebase_admin.initialize_app(cred)
        return _firebase_app
    except Exception as e:
        logger.error(f"Failed to initialize Firebase app: {e}")
        return None

async def send_feed_push(post: FeedPost) -> None:
    """Send FCM to relevant parents when a new announcement is posted."""
    app = _get_firebase_app()
    if not app:
        return

    # 1. Identify target parents
    query = {"role": UserRole.PARENT.value}
    
    # If not publish_to_all, filter by branch
    if post.target_branch_ids:
        # Get all parents who have at least one student in the target branches
        # This is a bit complex since student_ids are strings in User.
        # We'll first find students in those branches.
        students = await Student.find({"branch_id": {"$in": post.target_branch_ids}}).to_list()
        student_ids = [str(s.id) for s in students]
        query["student_ids"] = {"$in": student_ids}
    elif post.branch_id:
        students = await Student.find({"branch_id": post.branch_id}).to_list()
        student_ids = [str(s.id) for s in students]
        query["student_ids"] = {"$in": student_ids}

    parents = await User.find(query).to_list()
    
    # 2. Collect FCM tokens
    tokens = []
    for parent in parents:
        if parent.fcm_tokens:
            tokens.extend(parent.fcm_tokens)
    
    if not tokens:
        return

    # Check if this is an update (updated_at > created_at + 5 seconds buffer)
    is_update = (post.updated_at - post.created_at).total_seconds() > 5
    title = f"Update: {post.title}" if is_update else post.title

    # 3. Send notification
    # Batch send limit is 500
    for i in range(0, len(tokens), 500):
        batch = tokens[i:i+500]
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=post.content[:100] + "..." if len(post.content) > 100 else post.content,
            ),
            data={
                "type": "announcement",
                "id": str(post.id),
            },
            tokens=batch,
        )
        try:
            response = messaging.send_each_for_multicast(message)
            logger.info(f"Sent announcement notification to {response.success_count} devices. Errors: {response.failure_count}")
        except Exception as e:
            logger.error(f"FCM batch send failed: {e}")

async def send_attendance_notification(student: Student, log: AttendanceLog) -> None:
    """Notify parent of attendance update via FCM."""
    app = _get_firebase_app()
    if not app:
        return

    # Find parent(s) for this student
    parents = await User.find({"role": UserRole.PARENT.value, "student_ids": str(student.id)}).to_list()
    
    tokens = []
    for parent in parents:
        if parent.fcm_tokens:
            tokens.extend(parent.fcm_tokens)
            
    if not tokens:
        return

    status_text = "Present" if log.status == "present" else "Absent"
    title = f"Attendance: {student.full_name}"
    body = f"{student.full_name} has been marked {status_text} for {log.date.strftime('%d %b %Y')}."

    for i in range(0, len(tokens), 500):
        batch = tokens[i:i+500]
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data={
                "type": "attendance",
                "student_id": str(student.id),
            },
            tokens=batch,
        )
        try:
            messaging.send_each_for_multicast(message)
        except Exception as e:
            logger.error(f"FCM attendance notification failed: {e}")
