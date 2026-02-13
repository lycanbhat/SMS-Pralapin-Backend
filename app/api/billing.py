"""Fee management: status updates, receipt PDF, S3 storage."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from beanie import PydanticObjectId

from app.api.deps import CurrentUser, AdminOnly
from app.models.user import UserRole
from app.models.billing import Billing, BillingCreate, BillingPayBody, PaymentStatus
from app.models.student import Student
from app.models.branch import Branch
from app.models.settings import AppSettings
from app.services.receipt import generate_receipt_pdf, generate_receipt_pdf_bytes

router = APIRouter()


async def _receipt_context(b: Billing) -> dict | None:
    """Build receipt context: student_name, class_name, branch_name, components (list of (name, amount))."""
    student = await Student.get(b.student_id) if b.student_id else None
    branch = None
    if b.branch_id:
        try:
            branch = await Branch.get(PydanticObjectId(b.branch_id))
        except Exception:
            pass
    total = b.amount_paid
    components: list[tuple[str, float]] = []
    settings = await AppSettings.find_one()
    if settings and getattr(settings, "fee_structures", None):
        for fs in settings.fee_structures:
            if fs.name == b.fee_structure.name and fs.components:
                fixed_total = sum((c.amount or 0) for c in fs.components if c.type == "fixed")
                fee_base = max(0, total - fixed_total)
                for c in fs.components:
                    if c.type == "fixed":
                        amt = float(c.amount or 0)
                    else:
                        pct = float(c.percentage or 0)
                        amt = round(fee_base * pct / 100, 2)
                    components.append((c.name, amt))
                # Scale so component sum equals billing total (handles rounding / % != 100)
                comp_sum = sum(amt for _, amt in components)
                if comp_sum and abs(comp_sum - total) > 0.01:
                    scale = total / comp_sum
                    components = [(n, round(a * scale, 2)) for n, a in components]
                break
    if not components:
        components = [(b.fee_structure.name, total)]
    return {
        "student_name": student.full_name if student else "",
        "class_name": (student.class_name or student.class_id or "") if student else "",
        "branch_name": branch.name if branch else "",
        "components": components,
    }


@router.get("/")
async def list_billing(student_id: str | None = None, user: CurrentUser = ...):
    if user.role == UserRole.PARENT:
        if not student_id or student_id not in user.student_ids:
            raise HTTPException(status_code=403, detail="Not authorized")
    query = {}
    if student_id:
        query["student_id"] = student_id
    items = await Billing.find(query).to_list()
    return [
        {
            "id": str(b.id),
            "student_id": b.student_id,
            "fee_structure": b.fee_structure,
            "status": b.status.value,
            "amount_paid": b.amount_paid,
            "payment_mode": getattr(b, "payment_mode", "cash"),
            "transaction_number": getattr(b, "transaction_number", None),
            "receipt_url": b.receipt_url,
        }
        for b in items
    ]


@router.post("/", status_code=201)
async def create_billing(data: BillingCreate, user: AdminOnly):
    b = Billing(
        student_id=data.student_id,
        branch_id=data.branch_id,
        fee_structure=data.fee_structure,
        status=data.status,
    )
    await b.insert()
    return {"id": str(b.id)}


@router.patch("/{billing_id}/pay")
async def mark_paid(billing_id: str, body: BillingPayBody, user: AdminOnly):
    b = await Billing.get(PydanticObjectId(billing_id))
    if not b:
        raise HTTPException(status_code=404, detail="Billing not found")
    from datetime import datetime
    b.status = PaymentStatus.PAID
    b.amount_paid = body.amount_paid
    b.paid_at = datetime.utcnow()
    b.payment_mode = body.payment_mode if body.payment_mode in ("cash", "online") else "cash"
    b.transaction_number = body.transaction_number if body.payment_mode == "online" else None
    ctx = await _receipt_context(b)
    receipt_url = await generate_receipt_pdf(b, ctx)
    if receipt_url:
        b.receipt_url = receipt_url
    await b.save()
    return {"receipt_url": b.receipt_url}


@router.post("/{billing_id}/generate-receipt")
async def generate_receipt(billing_id: str, user: AdminOnly):
    """Generate PDF receipt for an existing paid billing record; upload to S3 if configured. Returns receipt_url or null (use GET /receipt to download)."""
    b = await Billing.get(PydanticObjectId(billing_id))
    if not b:
        raise HTTPException(status_code=404, detail="Billing not found")
    if b.status != PaymentStatus.PAID:
        raise HTTPException(status_code=400, detail="Only paid records can have a receipt generated")
    ctx = await _receipt_context(b)
    receipt_url = await generate_receipt_pdf(b, ctx)
    if receipt_url:
        b.receipt_url = receipt_url
        await b.save()
    return {"receipt_url": b.receipt_url}


@router.get("/{billing_id}/receipt")
async def download_receipt(billing_id: str, user: CurrentUser):
    """Generate receipt PDF on the fly (A5) and return as download. Works without S3 (e.g. local dev)."""
    b = await Billing.get(PydanticObjectId(billing_id))
    if not b:
        raise HTTPException(status_code=404, detail="Billing not found")
    if b.status != PaymentStatus.PAID:
        raise HTTPException(status_code=400, detail="Receipt only for paid records")
    if user.role == UserRole.PARENT and b.student_id not in (user.student_ids or []):
        raise HTTPException(status_code=403, detail="Not authorized")
    ctx = await _receipt_context(b)
    pdf_bytes = await generate_receipt_pdf_bytes(b, ctx)
    if not pdf_bytes:
        raise HTTPException(status_code=503, detail="Receipt generation failed")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="receipt.pdf"'},
    )
