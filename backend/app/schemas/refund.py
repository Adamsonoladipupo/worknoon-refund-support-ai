import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator

from app.policies.refund_policy import RefundReason


class RefundRequestCreate(BaseModel):
    """Request body for POST /api/refunds."""

    customer_id: uuid.UUID
    order_id: uuid.UUID
    # Decimal keeps money exact; the JSON number is coerced via Pydantic's
    # built-in Decimal handling — no float conversion occurs.
    requested_amount: Decimal
    reason: RefundReason

    @field_validator("requested_amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError("requested_amount must be greater than zero")
        return v

class AIRefundRequestCreate(BaseModel):
    """Request body for POST /api/refunds/ai."""

    customer_id: uuid.UUID
    order_id: uuid.UUID
    message: str

    @field_validator("message")
    @classmethod
    def message_must_not_be_empty(cls, v: str) -> str:
        value = v.strip()

        if not value:
            raise ValueError("message must not be empty")

        return value


class RefundRequestResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    order_id: uuid.UUID
    reason: str
    requested_amount: Decimal
    decision: str | None
    decision_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RefundSummaryResponse(BaseModel):
    """Response item for GET /api/refunds (admin dashboard list)."""

    id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str
    order_id: uuid.UUID
    order_number: str
    reason: str
    requested_amount: Decimal
    decision: str | None
    decision_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
