"""App settings and metadata (e.g. class options, fee structures)."""
from beanie import Document
from pydantic import BaseModel, Field


class FeeComponent(BaseModel):
    """A single fee line item: name, type; percentage for % type, amount for fixed."""
    name: str
    type: str  # "percentage" | "fixed"
    percentage: float | None = None  # For percentage type: % of (total_fees - fixed_total)
    amount: float | None = None  # For fixed type: default amount (used to compute Fixed total)


class FeeStructureItem(BaseModel):
    """One fee structure template: name, total fees, and list of components."""
    name: str
    total_fees: float | None = None  # Total fees (user input); Fee = total_fees - fixed_total
    components: list[FeeComponent] = Field(default_factory=list)


class AcademicYearConfig(BaseModel):
    """Configuration for calculating academic years."""
    start_month: int = 6  # June
    start_day: int = 1
    end_month: int = 5    # May
    end_day: int = 31


class BannerItem(BaseModel):
    """Banner item for mobile app (max 5)."""
    url: str
    s3_key: str
    is_active: bool = True


class AppSettings(Document):
    """Single-doc settings (id='main')."""

    class_options: list[str] = Field(default_factory=list)  # Class names for branch multi-select
    fee_structures: list[FeeStructureItem] = Field(default_factory=list)  # Multiple fee structure templates
    academic_year_config: AcademicYearConfig = Field(default_factory=AcademicYearConfig)
    cctv_enabled: bool = True  # Global toggle for parent CCTV access
    banners: list[BannerItem] = Field(default_factory=list)  # Mobile app banners (max 5)

    class Settings:
        name = "settings"
        use_state_management = True


class ClassOptionsUpdate(BaseModel):
    class_options: list[str] = Field(default_factory=list)


class FeeStructuresUpdate(BaseModel):
    fee_structures: list[FeeStructureItem] = Field(default_factory=list)


class CCTVConfigUpdate(BaseModel):
    cctv_enabled: bool


class BannerList(BaseModel):
    banners: list[BannerItem] = Field(default_factory=list)


class BannerListUpdate(BaseModel):
    banners: list[BannerItem] = Field(default_factory=list)
    max_banners: int = 5
