"""Announcement targeting, visibility, sorting and serialization helpers."""
from __future__ import annotations

import re
from typing import Iterable

from beanie import PydanticObjectId

from app.models.branch import Branch
from app.models.feed import FeedPost
from app.models.student import Student
from app.models.user import User

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTISPACE_RE = re.compile(r"\s+")
_HTML_IMG_SRC_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
_IMAGE_URL_RE = re.compile(r"(https?:\/\/\S+\.(?:png|jpg|jpeg|webp|gif))", re.IGNORECASE)


def safe_object_id(value: str | None) -> PydanticObjectId | None:
    if not value:
        return None
    try:
        return PydanticObjectId(value)
    except Exception:
        return None


def unique_branch_ids(values: Iterable[str] | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    if not values:
        return result
    for raw in values:
        branch_id = (raw or "").strip()
        if branch_id and branch_id not in seen:
            seen.add(branch_id)
            result.append(branch_id)
    return result


def plain_text_from_html(content_html: str) -> str:
    text = _HTML_TAG_RE.sub(" ", content_html or "")
    return _MULTISPACE_RE.sub(" ", text).strip()


def announcement_target_branch_ids(post: FeedPost) -> list[str]:
    branch_ids = unique_branch_ids(getattr(post, "target_branch_ids", []) or [])
    legacy_branch_id = (getattr(post, "branch_id", None) or "").strip()
    if legacy_branch_id and legacy_branch_id not in branch_ids:
        branch_ids.append(legacy_branch_id)
    return branch_ids


def is_announcement_visible(post: FeedPost, allowed_branch_ids: set[str]) -> bool:
    target_ids = announcement_target_branch_ids(post)
    if not target_ids:
        return True
    if not allowed_branch_ids:
        return False
    return bool(set(target_ids) & allowed_branch_ids)


async def parent_branch_ids(user: User) -> list[str]:
    student_ids: list[PydanticObjectId] = []
    for raw_student_id in user.student_ids:
        oid = safe_object_id(raw_student_id)
        if oid:
            student_ids.append(oid)

    if not student_ids:
        return []

    students = await Student.find(
        {
            "_id": {"$in": student_ids},
            "is_active": True,
        }
    ).to_list()
    return unique_branch_ids([s.branch_id for s in students if s.branch_id])


async def list_announcements_for_scope(allowed_branch_ids: set[str] | None) -> list[FeedPost]:
    posts = await FeedPost.find_all().to_list()
    if allowed_branch_ids is None:
        return posts
    return [p for p in posts if is_announcement_visible(p, allowed_branch_ids)]


def sort_announcements(posts: list[FeedPost]) -> list[FeedPost]:
    return sorted(
        posts,
        key=lambda p: (
            0 if p.is_pinned else 1,
            -(p.created_at.timestamp() if p.created_at else 0),
        ),
    )


async def build_author_name_map(posts: list[FeedPost]) -> dict[str, str]:
    author_oids: list[PydanticObjectId] = []
    seen: set[str] = set()
    for post in posts:
        raw_author_id = (post.author_id or "").strip()
        if not raw_author_id or raw_author_id in seen:
            continue
        oid = safe_object_id(raw_author_id)
        if oid:
            author_oids.append(oid)
            seen.add(raw_author_id)

    if not author_oids:
        return {}

    users = await User.find({"_id": {"$in": author_oids}}).to_list()
    return {str(u.id): u.full_name for u in users}


async def build_branch_name_map(posts: list[FeedPost]) -> dict[str, str]:
    all_branch_ids: list[str] = []
    for post in posts:
        all_branch_ids.extend(announcement_target_branch_ids(post))
    unique_ids = unique_branch_ids(all_branch_ids)
    if not unique_ids:
        return {}

    branch_oids: list[PydanticObjectId] = []
    for branch_id in unique_ids:
        oid = safe_object_id(branch_id)
        if oid:
            branch_oids.append(oid)
    if not branch_oids:
        return {}

    branches = await Branch.find({"_id": {"$in": branch_oids}}).to_list()
    return {str(b.id): b.name for b in branches}


def serialize_announcement(
    post: FeedPost,
    author_name_map: dict[str, str],
    branch_name_map: dict[str, str],
) -> dict:
    target_ids = announcement_target_branch_ids(post)
    plain_content = (post.content or "").strip()
    if not plain_content and (post.content_html or "").strip():
        plain_content = plain_text_from_html(post.content_html or "")

    image_url = None
    if (post.content_html or "").strip():
        img_match = _HTML_IMG_SRC_RE.search(post.content_html or "")
        if img_match:
            image_url = (img_match.group(1) or "").strip() or None
    if not image_url:
        url_match = _IMAGE_URL_RE.search(plain_content)
        if url_match:
            image_url = (url_match.group(1) or "").strip() or None

    return {
        "id": str(post.id),
        "title": post.title,
        "content": plain_content,
        "content_html": post.content_html,
        "image_url": image_url,
        "publish_to_all": len(target_ids) == 0,
        "target_branch_ids": target_ids,
        "target_branch_names": [branch_name_map.get(branch_id, branch_id) for branch_id in target_ids],
        "branch_id": (
            post.branch_id
            if post.branch_id
            else (target_ids[0] if len(target_ids) == 1 else None)
        ),
        "author_id": post.author_id,
        "author_name": author_name_map.get(post.author_id, ""),
        "is_pinned": post.is_pinned,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "updated_at": post.updated_at.isoformat() if post.updated_at else None,
    }
