from typing import List, Optional
from datetime import date
from fastapi import APIRouter, HTTPException, Query, Depends
from beanie import PydanticObjectId

from app.api.deps import TeacherOrAdmin, CurrentUser, AdminOnly
from app.models.holiday import Holiday, HolidayCreate, HolidayUpdate, HolidayOut
from app.models.user import UserRole
from app.services.academic_year import get_current_academic_year

router = APIRouter()

@router.get("/", response_model=List[HolidayOut])
async def list_holidays(
    user: CurrentUser,
    academic_year: Optional[str] = Query(None),
    branch_id: Optional[str] = Query(None)
):
    """List holidays, optionally filtered by academic year and branch."""
    query = {"is_active": True}
    if academic_year:
        query["academic_year"] = academic_year
    
    if branch_id:
        # Include holidays for specific branch OR global holidays (branch_id=None)
        query["$or"] = [{"branch_id": branch_id}, {"branch_id": None}]
    
    holidays = await Holiday.find(query).sort("date").to_list()
    return [
        {
            **h.model_dump(),
            "id": str(h.id)
        }
        for h in holidays
    ]

@router.post("/", response_model=HolidayOut)
async def create_holiday(data: HolidayCreate, user: TeacherOrAdmin):
    """Create a new holiday (Admin/Staff only)."""
    if not data.academic_year:
        data.academic_year = await get_current_academic_year()
    
    # If not admin, can only create for their own branch
    if user.role != UserRole.ADMIN:
        if data.branch_id and data.branch_id != user.branch_id:
            raise HTTPException(status_code=403, detail="Cannot create holiday for another branch")
        if not data.branch_id:
            # Teachers/Staff can't create global holidays
            data.branch_id = user.branch_id

    holiday = Holiday(**data.model_dump())
    await holiday.insert()
    return {
        **holiday.model_dump(),
        "id": str(holiday.id)
    }

@router.get("/{holiday_id}", response_model=HolidayOut)
async def get_holiday(holiday_id: str, user: CurrentUser):
    """Get holiday details."""
    holiday = await Holiday.get(PydanticObjectId(holiday_id))
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
    return {
        **holiday.model_dump(),
        "id": str(holiday.id)
    }

@router.patch("/{holiday_id}", response_model=HolidayOut)
async def update_holiday(holiday_id: str, data: HolidayUpdate, user: TeacherOrAdmin):
    """Update a holiday (Admin/Staff only)."""
    holiday = await Holiday.get(PydanticObjectId(holiday_id))
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
    
    # Permission check
    if user.role != UserRole.ADMIN:
        if holiday.branch_id != user.branch_id:
            raise HTTPException(status_code=403, detail="Cannot update holiday of another branch")
        if data.branch_id and data.branch_id != user.branch_id:
            raise HTTPException(status_code=403, detail="Cannot change branch to another branch")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(holiday, key, value)
    
    await holiday.save()
    return {
        **holiday.model_dump(),
        "id": str(holiday.id)
    }

@router.delete("/{holiday_id}", status_code=204)
async def delete_holiday(holiday_id: str, user: TeacherOrAdmin):
    """Deactivate (soft delete) a holiday."""
    holiday = await Holiday.get(PydanticObjectId(holiday_id))
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
    
    # Permission check
    if user.role != UserRole.ADMIN:
        if holiday.branch_id != user.branch_id:
            raise HTTPException(status_code=403, detail="Cannot delete holiday of another branch")

    holiday.is_active = False
    await holiday.save()
    return None
