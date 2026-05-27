"""Student CRUD - child info, class assignments."""
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from beanie import PydanticObjectId
from pydantic import BaseModel

from app.api.deps import CurrentUser, TeacherOrAdmin, AdminOnly, get_password_hash
from app.services.s3 import upload_student_document_to_s3, upload_student_photo_to_s3
from app.models.user import User, UserRole
from app.models.student import (
    Student,
    StudentCreate,
    StudentUpdate,
    GuardianInfo,
    EmergencyContact,
)
from app.services.academic_year import get_current_academic_year

router = APIRouter()


class ParentAccountRequest(BaseModel):
    password: str | None = None


async def _next_admission_number(branch_id: str) -> str:
    """Next admission number for branch (1, 2, 3... per branch)."""
    students = await Student.find(Student.branch_id == branch_id).to_list()
    existing = []
    for s in students:
        if s.admission_number and s.admission_number.isdigit():
            existing.append(int(s.admission_number))
    next_num = max(existing, default=0) + 1
    return str(next_num)


@router.get("/")
async def list_students(
    user: CurrentUser,
    branch_id: str | None = None,
    class_id: str | None = None,
    academic_year: str | None = None,
    q: str | None = Query(None, description="Search by name or roll number"),
):
    if user.role == UserRole.PARENT:
        if not user.student_ids:
            return []
        students = await Student.find(Student.id.in_([PydanticObjectId(s) for s in user.student_ids])).to_list()
        students = [s for s in students if s.is_active]
    else:
        query = {"is_active": True}
        if branch_id:
            query["branch_id"] = branch_id
        if class_id:
            query["class_id"] = class_id
        if q and q.strip():
            search = q.strip()
            query["$or"] = [
                {"full_name": {"$regex": search, "$options": "i"}},
                {"roll_number": {"$regex": search, "$options": "i"}},
            ]
        if academic_year and academic_year.strip():
            try:
                start_year = int(academic_year.split("-")[0])
                start_dt = datetime(start_year, 4, 1)
                end_dt = datetime(start_year + 1, 3, 31, 23, 59, 59)
                query["created_at"] = {"$gte": start_dt, "$lte": end_dt}
            except (ValueError, IndexError):
                pass
        students = await Student.find(query).to_list()
    return [
        {
            "id": str(s.id),
            "full_name": s.full_name,
            "photo_url": s.photo_url,
            "gender": s.gender,
            "branch_id": s.branch_id,
            "class_id": s.class_id,
            "class_name": s.class_name,
            "roll_number": s.roll_number,
            "admission_number": s.admission_number,
            "academic_year": s.academic_year,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in students
    ]


@router.post("/", status_code=201)
async def create_student(data: StudentCreate, user: TeacherOrAdmin):
    academic_year = await get_current_academic_year()
    admission_number = await _next_admission_number(data.branch_id)

    primary_guardian = None
    if data.primary_guardian:
        primary_guardian = GuardianInfo(
            name=data.primary_guardian.name,
            relationship=data.primary_guardian.relationship,
            relationship_other=data.primary_guardian.relationship_other,
            phone=data.primary_guardian.phone,
            email=data.primary_guardian.email,
        )

    secondary_guardian = None
    if data.secondary_guardian:
        secondary_guardian = GuardianInfo(
            name=data.secondary_guardian.name,
            relationship=data.secondary_guardian.relationship,
            relationship_other=data.secondary_guardian.relationship_other,
            phone=data.secondary_guardian.phone,
            email=data.secondary_guardian.email,
        )

    emergency_contact = None
    if data.emergency_contact:
        emergency_contact = EmergencyContact(
            name=data.emergency_contact.name,
            relationship=data.emergency_contact.relationship,
            phone=data.emergency_contact.phone,
        )

    s = Student(
        full_name=data.full_name,
        gender=data.gender,
        date_of_birth=data.date_of_birth,
        address=data.address,
        city=data.city,
        state=data.state,
        pincode=data.pincode,
        parent_user_id=(data.parent_user_id or ""),
        branch_id=data.branch_id,
        class_id=data.class_id,
        class_name=data.class_name,
        roll_number=data.roll_number,
        academic_year=academic_year,
        admission_number=admission_number,
        primary_guardian=primary_guardian,
        secondary_guardian=secondary_guardian,
        emergency_contact=emergency_contact,
    )
    await s.insert()
    return {"id": str(s.id), "full_name": s.full_name, "admission_number": admission_number, "academic_year": academic_year}


@router.get("/{student_id}")
async def get_student(student_id: str, user: CurrentUser):
    s = await Student.get(PydanticObjectId(student_id))
    if not s:
        raise HTTPException(status_code=404, detail="Student not found")
    if user.role == UserRole.PARENT and str(s.id) not in user.student_ids:
        raise HTTPException(status_code=403, detail="Not authorized for this student")
    return {
        "id": str(s.id),
        "full_name": s.full_name,
        "photo_url": s.photo_url,
        "gender": s.gender,
        "date_of_birth": s.date_of_birth,
        "address": s.address,
        "city": s.city,
        "state": s.state,
        "pincode": s.pincode,
        "parent_user_id": s.parent_user_id or None,
        "branch_id": s.branch_id,
        "class_id": s.class_id,
        "class_name": s.class_name,
        "roll_number": s.roll_number,
        "academic_year": s.academic_year,
        "admission_number": s.admission_number,
        "is_active": s.is_active,
        "primary_guardian": s.primary_guardian.model_dump() if s.primary_guardian else None,
        "secondary_guardian": s.secondary_guardian.model_dump() if s.secondary_guardian else None,
        "emergency_contact": s.emergency_contact.model_dump() if s.emergency_contact else None,
        "attendance_logs": s.attendance_logs,
        "documents": s.documents or {},
    }


@router.patch("/{student_id}")
async def update_student(student_id: str, data: StudentUpdate, user: TeacherOrAdmin):
    s = await Student.get(PydanticObjectId(student_id))
    if not s:
        raise HTTPException(status_code=404, detail="Student not found")
    update_data = data.model_dump(exclude_unset=True)
    if "primary_guardian" in update_data and update_data["primary_guardian"] is not None:
        update_data["primary_guardian"] = GuardianInfo(**update_data["primary_guardian"])
    elif "primary_guardian" in update_data and update_data["primary_guardian"] is None:
        pass
    if "secondary_guardian" in update_data and update_data["secondary_guardian"] is not None:
        update_data["secondary_guardian"] = GuardianInfo(**update_data["secondary_guardian"])
    if "emergency_contact" in update_data and update_data["emergency_contact"] is not None:
        update_data["emergency_contact"] = EmergencyContact(**update_data["emergency_contact"])
    for key, value in update_data.items():
        setattr(s, key, value)
    s.updated_at = datetime.utcnow()
    await s.save()
    out = {
        "id": str(s.id),
        "full_name": s.full_name,
        "photo_url": s.photo_url,
        "gender": s.gender,
        "date_of_birth": s.date_of_birth,
        "address": s.address,
        "city": s.city,
        "state": s.state,
        "pincode": s.pincode,
        "parent_user_id": s.parent_user_id or None,
        "branch_id": s.branch_id,
        "class_id": s.class_id,
        "class_name": s.class_name,
        "roll_number": s.roll_number,
        "academic_year": s.academic_year,
        "admission_number": s.admission_number,
        "is_active": s.is_active,
        "primary_guardian": s.primary_guardian.model_dump() if s.primary_guardian else None,
        "secondary_guardian": s.secondary_guardian.model_dump() if s.secondary_guardian else None,
        "emergency_contact": s.emergency_contact.model_dump() if s.emergency_contact else None,
        "attendance_logs": s.attendance_logs,
        "documents": s.documents or {},
    }
    return out


DOC_TYPES = {"birth_certificate", "guardian_aadhar", "address_proof"}


@router.post("/{student_id}/photo")
async def upload_student_photo(
    student_id: str,
    user: TeacherOrAdmin,
    file: UploadFile = File(...),
):
    """Upload student profile photo to S3 and set student.photo_url."""
    s = await Student.get(PydanticObjectId(student_id))
    if not s:
        raise HTTPException(status_code=404, detail="Student not found")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image (e.g. JPEG, PNG)")
    url, _ = await upload_student_photo_to_s3(file, student_id=student_id)
    s.photo_url = url
    s.updated_at = datetime.utcnow()
    await s.save()
    return {"photo_url": url}


@router.post("/{student_id}/documents/{doc_type}")
async def upload_student_document(
    student_id: str,
    doc_type: str,
    user: TeacherOrAdmin,
    file: UploadFile = File(...),
):
    """Upload a student document (birth_certificate, guardian_aadhar, address_proof) to S3."""
    if doc_type not in DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid doc_type. Must be one of: {', '.join(DOC_TYPES)}")
    s = await Student.get(PydanticObjectId(student_id))
    if not s:
        raise HTTPException(status_code=404, detail="Student not found")
    url, _ = await upload_student_document_to_s3(file, student_id=student_id, doc_type=doc_type)
    if not s.documents:
        s.documents = {}
    s.documents[doc_type] = url
    s.updated_at = datetime.utcnow()
    await s.save()
    return {"url": url, "doc_type": doc_type}


@router.delete("/{student_id}", status_code=204)
async def archive_student(student_id: str, user: TeacherOrAdmin):
    """Archive student (soft delete: set is_active=False)."""
    s = await Student.get(PydanticObjectId(student_id))
    if not s:
        raise HTTPException(status_code=404, detail="Student not found")
    s.is_active = False
    s.updated_at = datetime.utcnow()
    await s.save()


@router.post("/{student_id}/parent-account")
async def set_parent_account(student_id: str, data: ParentAccountRequest, admin: AdminOnly):
    """Create or update parent logins for this student using primary and secondary guardians."""
    s = await Student.get(PydanticObjectId(student_id))
    if not s:
        raise HTTPException(status_code=404, detail="Student not found")
    if not s.primary_guardian or not s.primary_guardian.phone or not s.primary_guardian.email:
        raise HTTPException(
            status_code=400,
            detail="Primary guardian's phone number and email are required to create parent login"
        )

    guardians_to_process = []
    if s.primary_guardian and s.primary_guardian.phone and s.primary_guardian.email:
        guardians_to_process.append(s.primary_guardian)
    if s.secondary_guardian and s.secondary_guardian.phone and s.secondary_guardian.email:
        guardians_to_process.append(s.secondary_guardian)

    primary_user_id = None
    created_or_updated_users = []

    for idx, guardian in enumerate(guardians_to_process):
        email = guardian.email
        full_name = guardian.name or s.full_name
        phone = guardian.phone

        user: User | None = None

        # Check if user already exists with this phone number.
        user = await User.find_one(User.role == UserRole.PARENT, User.phone == phone)

        # Otherwise, check by email.
        if not user:
            user = await User.find_one(User.role == UserRole.PARENT, User.email == email)

        # If still no user, create a new parent user.
        if not user:
            pwd = data.password if data.password else "OTP_LOGIN_ONLY_PLACEHOLDER"
            user = User(
                email=email,
                hashed_password=get_password_hash(pwd),
                role=UserRole.PARENT,
                full_name=full_name,
                phone=phone,
                student_ids=[str(s.id)],
                branch_id=s.branch_id,
                assigned_class_ids=[],
            )
            await user.insert()
        else:
            # Update details and ensure student is linked.
            if data.password:
                user.hashed_password = get_password_hash(data.password)
            if str(s.id) not in user.student_ids:
                user.student_ids.append(str(s.id))
            if not user.phone:
                user.phone = phone
            await user.save()

        if idx == 0:
            primary_user_id = str(user.id)
            
        created_or_updated_users.append({
            "user_id": str(user.id),
            "email": user.email,
            "phone": user.phone,
            "name": user.full_name,
        })

    if primary_user_id:
        s.parent_user_id = primary_user_id
        s.updated_at = datetime.utcnow()
        await s.save()

    return {
        "parent_user_id": primary_user_id,
        "users": created_or_updated_users,
    }
