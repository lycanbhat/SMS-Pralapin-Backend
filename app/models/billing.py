"""Fee structures, payment status, S3-hosted PDF receipts."""
from datetime import datetime
from enum import Enum
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    PARTIAL = "partial"
    WAIVED = "waived"


class FeeStructure(BaseModel):
    name: str
    amount: float
    due_date: Optional[str] = None
    period: Optional[str] = None  # e.g. "monthly", "quarterly"


class Billing(Document):
    """Billing document: fee structure, status, receipt PDF."""

    student_id: Indexed(str)
    branch_id: Indexed(str)
    fee_structure: FeeStructure
    status: PaymentStatus = PaymentStatus.PENDING
    amount_paid: float = 0.0
    paid_at: Optional[datetime] = None
    payment_mode: str = "cash"  # "cash" | "online"
    transaction_number: Optional[str] = None  # for online payments
    receipt_s3_key: Optional[str] = None
    receipt_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BillingPayBody(BaseModel):
    amount_paid: float
    payment_mode: str = "cash"  # "cash" | "online"
    transaction_number: Optional[str] = None

    class Settings:
        name = "billing"
        use_state_management = True


class BillingCreate(BaseModel):
    student_id: str
    branch_id: str
    fee_structure: FeeStructure
    status: PaymentStatus = PaymentStatus.PENDING
