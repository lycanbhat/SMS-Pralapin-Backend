from datetime import datetime, date
from app.models.settings import AppSettings
from app.models.academic_year import AcademicYear

async def ensure_academic_year():
    """
    Ensure the current academic year record exists in the database.
    Calculates based on AppSettings.academic_year_config.
    Mark only one as current.
    """
    settings = await AppSettings.find_one()
    if not settings:
        # Should not happen as we seed or it's created on first access
        # But let's handle it gracefully
        return

    config = settings.academic_year_config
    now = datetime.utcnow()
    
    # Logic to determine which academic year we are currently in
    # Example: Start June 1, End May 31.
    # If today is Feb 2026, we are in 2025-26.
    # If today is June 2026, we are in 2026-27.
    
    current_year = now.year
    start_of_possible_current = datetime(current_year, config.start_month, config.start_day)
    
    if now < start_of_possible_current:
        # We haven't reached the start of the "current" year yet, 
        # so the academic year started last year.
        academic_year_start_year = current_year - 1
    else:
        academic_year_start_year = current_year
        
    academic_year_name = f"{academic_year_start_year}-{(academic_year_start_year + 1) % 100:02d}"
    
    # Check if this record exists
    existing = await AcademicYear.find_one(AcademicYear.name == academic_year_name)
    
    if not existing:
        # Create it
        start_dt = datetime(academic_year_start_year, config.start_month, config.start_day)
        # End date logic: handle year wrap around
        end_year = academic_year_start_year + (1 if config.end_month < config.start_month else 0)
        end_dt = datetime(end_year, config.end_month, config.end_day, 23, 59, 59)
        
        new_ay = AcademicYear(
            name=academic_year_name,
            start_date=start_dt,
            end_date=end_dt,
            is_current=True
        )
        await new_ay.insert()
        
        # Unmark others as current
        await AcademicYear.find(AcademicYear.name != academic_year_name).update({"$set": {"is_current": False}})
    else:
        if not existing.is_current:
            existing.is_current = True
            await existing.save()
            # Unmark others as current
            await AcademicYear.find(AcademicYear.name != academic_year_name).update({"$set": {"is_current": False}})

async def get_current_academic_year() -> str:
    ay = await AcademicYear.find_one(AcademicYear.is_current == True)
    if ay:
        return ay.name
    return "Unknown"
