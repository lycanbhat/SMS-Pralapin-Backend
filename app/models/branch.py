"""Branch metadata and CCTV stream configurations."""
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field


class ClassFeeStructureMapping(BaseModel):
    """Maps a class offered at the branch to a fee structure (by name) with timings."""
    class_name: str
    fee_structure_name: str
    start_time: Optional[str] = "09:00"  # HH:MM format
    end_time: Optional[str] = "13:00"    # HH:MM format


class CCTVConfig(BaseModel):
    """Per-location CCTV stream config (RTSP -> HLS)."""
    stream_id: str
    name: str
    hls_playlist_url: str  # After transcoding RTSP -> HLS
    token_secret: str  # For signed URL generation
    enabled: bool = True


class Branch(Document):
    """Branch/location with CCTV configs."""

    name: Indexed(str)
    code: str = ""  # optional, e.g. "BLR-01"
    classes: list[str] = Field(default_factory=list)  # selected from settings class_options
    class_fee_structures: list[ClassFeeStructureMapping] = Field(default_factory=list)  # class -> fee structure name
    google_location: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    phone: Optional[str] = None
    coordinator_id: Optional[str] = None  # user id
    is_active: bool = True
    cctv_configs: list[CCTVConfig] = Field(default_factory=list)

    class Settings:
        name = "branches"
        use_state_management = True


class BranchCreate(BaseModel):
    """Only name is required when creating; rest editable from branch details."""
    name: str
    code: Optional[str] = None


class BranchUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    classes: Optional[list[str]] = None
    class_fee_structures: Optional[list[ClassFeeStructureMapping]] = None
    google_location: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    phone: Optional[str] = None
    coordinator_id: Optional[str] = None
    cctv_configs: Optional[list[CCTVConfig]] = None
