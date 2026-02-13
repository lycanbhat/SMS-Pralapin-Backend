"""Branches/locations - create with name only; full data editable on detail."""
from fastapi import APIRouter, HTTPException
from beanie import PydanticObjectId

from app.api.deps import AdminOnly, CurrentUser
from app.models.branch import Branch, BranchCreate, BranchUpdate

router = APIRouter()


@router.get("/")
async def list_branches(user: CurrentUser):
    branches = await Branch.find(Branch.is_active == True).to_list()
    return [
        {
            "id": str(b.id),
            "name": b.name,
            "code": b.code or "",
            "classes": getattr(b, "classes", []) or [],
            "class_fee_structures": [
                {
                    "class_name": m.class_name, 
                    "fee_structure_name": m.fee_structure_name,
                    "start_time": m.start_time,
                    "end_time": m.end_time,
                } for m in getattr(b, "class_fee_structures", []) or []
            ],
            "google_location": getattr(b, "google_location", None),
            "address": b.address,
            "city": getattr(b, "city", None),
            "state": getattr(b, "state", None),
            "pincode": getattr(b, "pincode", None),
            "phone": b.phone,
            "coordinator_id": getattr(b, "coordinator_id", None),
            "cctv_configs": [{"stream_id": c.stream_id, "name": c.name} for c in b.cctv_configs],
        }
        for b in branches
    ]


@router.post("/", status_code=201)
async def create_branch(data: BranchCreate, user: AdminOnly):
    code = (data.code or "").strip().upper() or None
    b = Branch(
        name=data.name.strip(),
        code=code or "",
        classes=[],
    )
    await b.insert()
    return {"id": str(b.id), "name": b.name, "code": b.code}


@router.get("/{branch_id}")
async def get_branch(branch_id: str, user: CurrentUser):
    b = await Branch.get(PydanticObjectId(branch_id))
    if not b:
        raise HTTPException(status_code=404, detail="Branch not found")
    return {
        "id": str(b.id),
        "name": b.name,
        "code": b.code or "",
        "classes": getattr(b, "classes", []) or [],
        "class_fee_structures": [
            {
                "class_name": m.class_name, 
                "fee_structure_name": m.fee_structure_name,
                "start_time": m.start_time,
                "end_time": m.end_time,
            } for m in getattr(b, "class_fee_structures", []) or []
        ],
        "google_location": getattr(b, "google_location", None),
        "address": b.address,
        "city": getattr(b, "city", None),
        "state": getattr(b, "state", None),
        "pincode": getattr(b, "pincode", None),
        "phone": b.phone,
        "coordinator_id": getattr(b, "coordinator_id", None),
        "cctv_configs": [{"stream_id": c.stream_id, "name": c.name} for c in b.cctv_configs],
    }


@router.patch("/{branch_id}")
async def update_branch(branch_id: str, data: BranchUpdate, user: AdminOnly):
    b = await Branch.get(PydanticObjectId(branch_id))
    if not b:
        raise HTTPException(status_code=404, detail="Branch not found")
    update = data.model_dump(exclude_unset=True)
    if "class_fee_structures" in update:
        update["classes"] = [m["class_name"] for m in update["class_fee_structures"]]
    for key, value in update.items():
        setattr(b, key, value)
    await b.save()
    return {
        "id": str(b.id),
        "name": b.name,
        "code": b.code or "",
        "classes": getattr(b, "classes", []) or [],
        "class_fee_structures": [
            {
                "class_name": m.class_name, 
                "fee_structure_name": m.fee_structure_name,
                "start_time": m.start_time,
                "end_time": m.end_time,
            } for m in getattr(b, "class_fee_structures", []) or []
        ],
        "google_location": getattr(b, "google_location", None),
        "address": b.address,
        "city": getattr(b, "city", None),
        "state": getattr(b, "state", None),
        "pincode": getattr(b, "pincode", None),
        "phone": b.phone,
        "coordinator_id": getattr(b, "coordinator_id", None),
    }
