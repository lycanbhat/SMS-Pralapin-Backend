"""App settings - class options and fee structure metadata."""
from fastapi import APIRouter, HTTPException
from app.api.deps import AdminOnly, CurrentUser
from app.models.settings import AppSettings, ClassOptionsUpdate, FeeStructuresUpdate, AcademicYearConfig, CCTVConfigUpdate
from app.models.academic_year import AcademicYear, AcademicYearConfigUpdate
from app.services.academic_year import ensure_academic_year

router = APIRouter()


@router.get("/academic-years")
async def list_academic_years(user: CurrentUser):
    """List all generated academic years."""
    return await AcademicYear.find_all().sort("name").to_list()


@router.get("/academic-years/current")
async def get_current_ay(user: CurrentUser):
    """Get the current academic year record."""
    ay = await AcademicYear.find_one(AcademicYear.is_current == True)
    if not ay:
        # If none marked current, try to ensure one exists
        await ensure_academic_year()
        ay = await AcademicYear.find_one(AcademicYear.is_current == True)
        if not ay:
            raise HTTPException(status_code=404, detail="No current academic year set")
    return ay


@router.get("/academic-year-config")
async def get_ay_config(admin: AdminOnly):
    """Get academic year configuration."""
    settings = await AppSettings.find_one()
    return settings.academic_year_config if settings else AcademicYearConfig()


@router.post("/academic-year-config")
async def update_ay_config(data: AcademicYearConfigUpdate, admin: AdminOnly):
    """Update academic year configuration and trigger re-generation."""
    settings = await AppSettings.find_one()
    if not settings:
        settings = AppSettings()
        await settings.insert()
    
    settings.academic_year_config = AcademicYearConfig(**data.model_dump())
    await settings.save()
    
    # Trigger re-calculation/re-generation
    await ensure_academic_year()
    
    return settings.academic_year_config


@router.get("/class-options")
async def get_class_options(user: CurrentUser):
    settings = await AppSettings.find_one()
    if not settings:
        return {"class_options": []}
    return {"class_options": settings.class_options}


@router.put("/class-options")
async def update_class_options(data: ClassOptionsUpdate, user: AdminOnly):
    settings = await AppSettings.find_one()
    if not settings:
        settings = AppSettings(class_options=data.class_options)
        await settings.insert()
    else:
        settings.class_options = data.class_options
        await settings.save()
    return {"class_options": settings.class_options}


@router.get("/fee-structures")
async def get_fee_structures(user: CurrentUser):
    settings = await AppSettings.find_one()
    if not settings:
        return {"fee_structures": []}
    # Backward compat: old fee_structure (single list) becomes one fee structure
    old = getattr(settings, "fee_structure", None)
    if old is not None and isinstance(old, list) and len(old) > 0:
        return {"fee_structures": [{"name": "Default", "components": old}]}
    return {"fee_structures": getattr(settings, "fee_structures", [])}


@router.put("/fee-structures")
async def update_fee_structures(data: FeeStructuresUpdate, user: AdminOnly):
    settings = await AppSettings.find_one()
    if not settings:
        settings = AppSettings(fee_structures=data.fee_structures)
        await settings.insert()
    else:
        settings.fee_structures = data.fee_structures
        await settings.save()
    return {"fee_structures": settings.fee_structures}


@router.get("/cctv-config")
async def get_cctv_config(user: CurrentUser):
    settings = await AppSettings.find_one()
    return {"cctv_enabled": settings.cctv_enabled if settings else True}


@router.put("/cctv-config")
async def update_cctv_config(data: CCTVConfigUpdate, user: AdminOnly):
    settings = await AppSettings.find_one()
    if not settings:
        settings = AppSettings(cctv_enabled=data.cctv_enabled)
        await settings.insert()
    else:
        settings.cctv_enabled = data.cctv_enabled
        await settings.save()
    return {"cctv_enabled": settings.cctv_enabled}
