"""Announcements & News Room - rich text posts with branch targeting."""
from datetime import datetime

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, TeacherOrAdmin
from app.models.branch import Branch
from app.models.feed import FeedPost, FeedPostCreate, FeedPostUpdate
from app.models.user import User, UserRole
from app.services.announcements import (
    build_author_name_map,
    build_branch_name_map,
    is_announcement_visible,
    list_announcements_for_scope,
    parent_branch_ids,
    plain_text_from_html,
    safe_object_id,
    serialize_announcement,
    sort_announcements,
    unique_branch_ids,
)
from app.services.fcm import send_feed_push

router = APIRouter()


def _resolve_target_branches(payload: FeedPostCreate) -> list[str]:
    target_ids = unique_branch_ids(payload.target_branch_ids)
    legacy_branch_id = (payload.branch_id or "").strip()
    if legacy_branch_id and legacy_branch_id not in target_ids:
        target_ids.append(legacy_branch_id)
    if payload.publish_to_all:
        return []
    return target_ids


async def _validate_branch_ids(target_branch_ids: list[str]) -> None:
    if not target_branch_ids:
        return
    branch_oids: list[PydanticObjectId] = []
    for branch_id in target_branch_ids:
        oid = safe_object_id(branch_id)
        if not oid:
            raise HTTPException(status_code=400, detail=f"Invalid branch_id: {branch_id}")
        branch_oids.append(oid)

    branches = await Branch.find({"_id": {"$in": branch_oids}}).to_list()
    found = {str(branch.id) for branch in branches}
    missing = [branch_id for branch_id in target_branch_ids if branch_id not in found]
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown branch_id(s): {', '.join(missing)}")


async def _visible_posts_for_user(user: CurrentUser, branch_id: str | None) -> list[FeedPost]:
    if user.role == UserRole.PARENT:
        allowed_branch_ids = set(await parent_branch_ids(user))
        if branch_id:
            if branch_id not in allowed_branch_ids:
                raise HTTPException(status_code=403, detail="Not authorized for this branch")
            allowed_branch_ids = {branch_id}
        return await list_announcements_for_scope(allowed_branch_ids)

    if branch_id:
        return await list_announcements_for_scope({branch_id})
    return await list_announcements_for_scope(None)


async def _serialize_posts(posts: list[FeedPost]) -> list[dict]:
    author_name_map = await build_author_name_map(posts)
    branch_name_map = await build_branch_name_map(posts)
    return [serialize_announcement(post, author_name_map, branch_name_map) for post in posts]


async def _create_post(payload: FeedPostCreate, user: TeacherOrAdmin) -> FeedPost:
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    target_branch_ids = _resolve_target_branches(payload)
    await _validate_branch_ids(target_branch_ids)

    content_html = (payload.content_html or "").strip() or None
    content = (payload.content or "").strip()
    if not content and content_html:
        content = plain_text_from_html(content_html)

    post = FeedPost(
        branch_id=(target_branch_ids[0] if len(target_branch_ids) == 1 else None),
        target_branch_ids=target_branch_ids,
        title=title,
        content=content,
        content_html=content_html,
        author_id=payload.author_id or str(user.id),
        is_pinned=payload.is_pinned,
        updated_at=datetime.utcnow(),
    )
    await post.insert()
    await send_feed_push(post)
    return post


@router.get("/")
async def list_feed(
    branch_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = ...,
):
    posts = await _visible_posts_for_user(user, branch_id)
    posts = sort_announcements(posts)
    page = posts[offset : offset + limit]
    return await _serialize_posts(page)


@router.get("/announcements")
async def list_announcements(
    branch_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = ...,
):
    posts = await _visible_posts_for_user(user, branch_id)
    posts = sort_announcements(posts)
    total = len(posts)
    page = posts[offset : offset + limit]
    return {
        "items": await _serialize_posts(page),
        "limit": limit,
        "offset": offset,
        "total": total,
    }


@router.get("/announcements/{post_id}")
async def get_announcement(post_id: str, user: CurrentUser):
    post_oid = safe_object_id(post_id)
    if not post_oid:
        raise HTTPException(status_code=400, detail="Invalid post_id")

    post = await FeedPost.get(post_oid)
    if not post:
        raise HTTPException(status_code=404, detail="Announcement not found")

    if user.role == UserRole.PARENT:
        allowed_branch_ids = set(await parent_branch_ids(user))
        if not is_announcement_visible(post, allowed_branch_ids):
            raise HTTPException(status_code=403, detail="Not authorized for this announcement")

    items = await _serialize_posts([post])
    result = items[0]
    
    # Add analytics for admin/teacher
    if user.role != UserRole.PARENT:
        total_fcm_users = await User.find({"fcm_tokens": {"$exists": True, "$not": {"$size": 0}}}).count()
        result["analytics"] = {
            "total_fcm_users": total_fcm_users,
            "click_count": post.click_count,
            "view_count": post.view_count,
            "unique_viewers": len(post.viewer_ids)
        }
    return result


@router.post("/announcements/{post_id}/track")
async def track_announcement(post_id: str, action: str, user: CurrentUser):
    """Track clicks and views for an announcement."""
    post_oid = safe_object_id(post_id)
    if not post_oid:
        raise HTTPException(status_code=400, detail="Invalid post_id")

    post = await FeedPost.get(post_oid)
    if not post:
        raise HTTPException(status_code=404, detail="Announcement not found")

    if action == "click":
        post.click_count += 1
    elif action == "view":
        post.view_count += 1
        user_id = str(user.id)
        if user_id not in post.viewer_ids:
            post.viewer_ids.append(user_id)
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    await post.save()
    return {"status": "ok"}


@router.post("/", status_code=201)
async def create_post(payload: FeedPostCreate, user: TeacherOrAdmin):
    post = await _create_post(payload, user)
    return {"id": str(post.id), "title": post.title}


@router.post("/announcements", status_code=201)
async def create_announcement(payload: FeedPostCreate, user: TeacherOrAdmin):
    post = await _create_post(payload, user)
    items = await _serialize_posts([post])
    return items[0]


@router.patch("/announcements/{post_id}")
async def update_announcement(post_id: str, payload: FeedPostUpdate, user: TeacherOrAdmin):
    post_oid = safe_object_id(post_id)
    if not post_oid:
        raise HTTPException(status_code=400, detail="Invalid post_id")

    post = await FeedPost.get(post_oid)
    if not post:
        raise HTTPException(status_code=404, detail="Announcement not found")

    update_data = payload.model_dump(exclude_unset=True)
    
    if "publish_to_all" in update_data or "target_branch_ids" in update_data or "branch_id" in update_data:
        # Re-resolve branches if targeting changed
        # We need a pseudo-create object to use the existing resolver
        resolve_payload = FeedPostCreate(
            title=update_data.get("title", post.title),
            content=update_data.get("content", post.content),
            content_html=update_data.get("content_html", post.content_html),
            publish_to_all=update_data.get("publish_to_all", len(post.target_branch_ids) == 0),
            target_branch_ids=update_data.get("target_branch_ids", post.target_branch_ids),
            branch_id=update_data.get("branch_id", post.branch_id),
            is_pinned=update_data.get("is_pinned", post.is_pinned)
        )
        target_branch_ids = _resolve_target_branches(resolve_payload)
        await _validate_branch_ids(target_branch_ids)
        post.target_branch_ids = target_branch_ids
        post.branch_id = (target_branch_ids[0] if len(target_branch_ids) == 1 else None)

    if "title" in update_data:
        post.title = update_data["title"]
    if "content" in update_data:
        post.content = update_data["content"]
    if "content_html" in update_data:
        post.content_html = update_data["content_html"]
        if not update_data.get("content"):
            post.content = plain_text_from_html(update_data["content_html"])
    if "is_pinned" in update_data:
        post.is_pinned = update_data["is_pinned"]

    post.updated_at = datetime.utcnow()
    await post.save()
    
    # Trigger notification for update
    await send_feed_push(post)
    
    items = await _serialize_posts([post])
    return items[0]


@router.delete("/announcements/{post_id}", status_code=204)
async def delete_announcement(post_id: str, user: TeacherOrAdmin):
    post_oid = safe_object_id(post_id)
    if not post_oid:
        raise HTTPException(status_code=400, detail="Invalid post_id")

    post = await FeedPost.get(post_oid)
    if not post:
        raise HTTPException(status_code=404, detail="Announcement not found")

    await post.delete()
    return None
