"""Firebase Cloud Messaging: feed announcements and attendance notifications."""
import asyncio
import firebase_admin
from firebase_admin import credentials, messaging
from typing import Optional, List
import logging

from app.models.feed import FeedPost
from app.models.student import Student, AttendanceLog
from app.models.user import User, UserRole
from app.models.homework import Homework
from app.config import settings

logger = logging.getLogger(__name__)

_firebase_app = None

def _get_firebase_app():
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    if not (settings.firebase_credentials_path and settings.firebase_credentials_path.strip()):
        logger.warning(
            "FIREBASE_CREDENTIALS_PATH is not set. Push notifications are disabled. "
            "Set it to the path of your Firebase service account JSON (e.g. in .env)."
        )
        return None

    try:
        cred = credentials.Certificate(settings.firebase_credentials_path.strip())
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase app initialized for FCM.")
        return _firebase_app
    except Exception as e:
        logger.error(f"Failed to initialize Firebase app: {e}")
        return None

def _send_multicast_sync(message: messaging.MulticastMessage) -> Optional[messaging.BatchResponse]:
    """Synchronous FCM send (Firebase SDK is blocking). Call from thread."""
    try:
        return messaging.send_each_for_multicast(message)
    except Exception as e:
        logger.error(f"FCM send_each_for_multicast failed: {e}")
        return None

async def send_feed_push(post: FeedPost) -> None:
    """Send FCM to relevant parents when a new announcement is posted."""
    app = _get_firebase_app()
    if not app:
        logger.warning("Announcement created but FCM skipped: Firebase not configured.")
        return

    # 1. Identify target parents
    query = {"role": UserRole.PARENT.value}

    if post.target_branch_ids:
        students = await Student.find({"branch_id": {"$in": post.target_branch_ids}}).to_list()
        student_ids = [str(s.id) for s in students]
        query["student_ids"] = {"$in": student_ids}
    elif post.branch_id:
        students = await Student.find({"branch_id": post.branch_id}).to_list()
        student_ids = [str(s.id) for s in students]
        query["student_ids"] = {"$in": student_ids}

    parents = await User.find(query).to_list()

    # 2. Collect FCM tokens and map token -> user (so we can remove invalid tokens later)
    tokens: List[str] = []
    token_to_user: dict[str, User] = {}
    for parent in parents:
        for token in (getattr(parent, "fcm_tokens", None) or []):
            tokens.append(token)
            token_to_user[token] = parent

    if not tokens:
        logger.warning(
            "Announcement created but no FCM tokens found. "
            "Parents must open the mobile app (logged in) so their device token is registered."
        )
        return

    logger.info(f"Sending announcement push to {len(tokens)} token(s) ({len(parents)} parent(s)).")

    is_update = (post.updated_at - post.created_at).total_seconds() > 5
    notif_title = f"Update: {post.title}" if is_update else post.title
    body_text = (post.content or "").strip()
    if len(body_text) > 100:
        body_text = body_text[:100] + "..."
    if not body_text:
        body_text = "New announcement"

    notification = messaging.Notification(title=notif_title, body=body_text)
    data = {"type": "announcement", "id": str(post.id)}

    loop = asyncio.get_event_loop()
    for i in range(0, len(tokens), 500):
        batch = tokens[i : i + 500]
        batch_message = messaging.MulticastMessage(
            notification=notification,
            data=data,
            tokens=batch,
        )
        response = await loop.run_in_executor(
            None, lambda m=batch_message: _send_multicast_sync(m)
        )
        if response:
            logger.info(
                f"Announcement push: success={response.success_count}, failure={response.failure_count}"
            )
            # Remove invalid/expired tokens from user documents so we don't retry or spam logs
            if response.failure_count > 0 and response.responses:
                for j, send_response in enumerate(response.responses):
                    if not send_response.success and j < len(batch):
                        failed_token = batch[j]
                        user = token_to_user.get(failed_token)
                        if user and failed_token in getattr(user, "fcm_tokens", []):
                            user.fcm_tokens = [t for t in user.fcm_tokens if t != failed_token]
                            await user.save()
                            logger.info(
                                "Removed invalid FCM token for user %s (%s). "
                                "Next app open will re-register.",
                                user.email,
                                send_response.exception,
                            )

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


async def send_homework_notification(hw: Homework) -> None:
    """Notify parents when homework is added for a class.

    Title format: "<Child's name>'s homework for <added date>"
    Body: homework title.
    """
    app = _get_firebase_app()
    if not app:
        return

    # Find students in this class + branch
    students = await Student.find(
        {"branch_id": hw.branch_id, "class_id": hw.class_id, "is_active": True}
    ).to_list()
    if not students:
        return

    # For each student, send personalised notification to their parents
    for student in students:
        parents = await User.find(
            {
                "role": UserRole.PARENT.value,
                "student_ids": str(student.id),
            }
        ).to_list()

        tokens: List[str] = []
        for parent in parents:
            if parent.fcm_tokens:
                tokens.extend(parent.fcm_tokens)

        if not tokens:
            continue

        date_text = (
            hw.date.strftime("%d %b %Y") if hasattr(hw.date, "strftime") else str(hw.date)
        )
        title = f"{student.full_name}'s homework for {date_text}"
        body = hw.title

        for i in range(0, len(tokens), 500):
            batch = tokens[i : i + 500]
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data={
                    "type": "homework",
                    "homework_id": str(hw.id),
                    "student_id": str(student.id),
                    "class_id": hw.class_id,
                    "date": str(hw.date),
                },
                tokens=batch,
            )
            try:
                messaging.send_each_for_multicast(message)
            except Exception as e:
                logger.error(f"FCM homework notification failed: {e}")
