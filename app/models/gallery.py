from datetime import datetime
from typing import Optional, List
from beanie import Document, Indexed
from pydantic import BaseModel, Field

class Photo(BaseModel):
    id: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y%m%d%H%M%S%f"))
    url: str
    key: str  # S3 key
    caption: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    uploaded_by: str  # user id

class Album(Document):
    name: Indexed(str)
    description: Optional[str] = None
    branch_id: Optional[str] = None  # None = visible to all
    cover_image_url: Optional[str] = None
    photos: List[Photo] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str

    class Settings:
        name = "albums"
        use_state_management = True

class AlbumCreate(BaseModel):
    name: str
    description: Optional[str] = None
    branch_id: Optional[str] = None

class AlbumUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    branch_id: Optional[str] = None
    cover_image_url: Optional[str] = None
