"""Announcements & News Room - FCM push on publish."""
from datetime import datetime
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field, model_validator


class FeedPost(Document):
    """Announcement/News post; triggers FCM to Flutter on create."""

    # Legacy single-branch field; preserved for backward compatibility.
    branch_id: Optional[str] = None  # None = all branches
    # New targeting field; empty list means all branches.
    target_branch_ids: list[str] = Field(default_factory=list)
    title: str
    # Plain text version used by clients that do not render rich text.
    content: str = ""
    # Rich text HTML from web editor (optional, but recommended).
    content_html: Optional[str] = None
    author_id: Indexed(str)
    is_pinned: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Analytics
    click_count: int = 0
    view_count: int = 0
    viewer_ids: list[str] = Field(default_factory=list)

    class Settings:
        name = "feed"
        use_state_management = True


class FeedPostCreate(BaseModel):
    title: str
    content: Optional[str] = None
    content_html: Optional[str] = None
    author_id: Optional[str] = None
    branch_id: Optional[str] = None
    publish_to_all: bool = True
    target_branch_ids: list[str] = Field(default_factory=list)
    is_pinned: bool = False

    @model_validator(mode="after")
    def validate_payload(self):
        has_plain = bool((self.content or "").strip())
        has_rich = bool((self.content_html or "").strip())
        if not has_plain and not has_rich:
            raise ValueError("Either content or content_html is required")

        if not self.publish_to_all:
            has_legacy_branch = bool((self.branch_id or "").strip())
            has_target_list = any((item or "").strip() for item in self.target_branch_ids)
            if not has_legacy_branch and not has_target_list:
                raise ValueError(
                    "Provide branch_id or target_branch_ids when publish_to_all is false"
                )
        return self


class FeedPostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    content_html: Optional[str] = None
    branch_id: Optional[str] = None
    publish_to_all: Optional[bool] = None
    target_branch_ids: Optional[list[str]] = None
    is_pinned: Optional[bool] = None
