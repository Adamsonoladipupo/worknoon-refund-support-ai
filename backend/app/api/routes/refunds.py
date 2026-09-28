from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.exceptions import AIServiceConfigError, AIServiceError
from app.schemas.refund import (
    AIRefundRequestCreate,
    RefundRequestCreate,
    RefundRequestResponse,
    RefundSummaryResponse,
)

from app.ai.service import AIService

from app.core.exceptions import (
    CustomerNotFoundError,
    InvalidRefundAmountError,
    OrderNotFoundError,
)
from app.database.connection import get_db
from app.repositories.refund_repository import RefundRepository
from app.services.refund_service import RefundService

router = APIRouter(prefix="/refunds", tags=["refunds"])


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/refunds — Admin / support dashboard list
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=list[RefundSummaryResponse],
    status_code=status.HTTP_200_OK,
    summary="List recent refund requests (admin dashboard)",
    description=(
        "Returns the most recent refund requests with customer and order "
        "context for the admin/support dashboard. Results are ordered newest "
        "first. Maximum 200 records per request."
    ),
)
async def list_refunds(
    limit: int = Query(default=50, ge=1, le=200, description="Max records to return"),
    db: AsyncSession = Depends(get_db),
) -> list[RefundSummaryResponse]:
    repo = RefundRepository(db)
    records = await repo.list_recent(limit=limit)

    return [
        RefundSummaryResponse(
            id=r.id,
            customer_id=r.customer_id,
            customer_name=r.customer.name,
            order_id=r.order_id,
            order_number=r.order.order_number,
            reason=r.reason,
            requested_amount=r.requested_amount,
            decision=r.decision,
            decision_reason=r.decision_reason,
            created_at=r.created_at,
        )
        for r in records
    ]


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/refunds — Submit a structured refund request
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=RefundRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a refund request",
    description=(
        "Processes a refund request through the policy engine and persists the "
        "result. Returns 201 with the created record regardless of whether the "
        "decision is APPROVED, DENIED, or ESCALATED — the decision is part of "
        "the response body."
    ),
)
async def create_refund(
    body: RefundRequestCreate,
    db: AsyncSession = Depends(get_db),
) -> RefundRequestResponse:
    service = RefundService(db)
    try:
        refund_request = await service.process_refund(
            customer_id=body.customer_id,
            order_id=body.order_id,
            requested_amount=body.requested_amount,
            reason=body.reason,
        )
    except CustomerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except OrderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidRefundAmountError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return RefundRequestResponse.model_validate(refund_request)


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/refunds/ai — Submit a natural-language refund request
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/ai",
    response_model=RefundRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a natural-language refund request",
    description=(
        "Uses Google Gemini to extract the refund reason and requested amount "
        "from a customer message, then passes the extracted data through the "
        "deterministic refund policy."
    ),
)
async def create_ai_refund(
        body: AIRefundRequestCreate,
        db: AsyncSession = Depends(get_db),
) -> RefundRequestResponse:
    try:
        service = RefundService(
            db,
            ai_service=AIService(),
        )

        refund_request = await service.process_ai_refund(
            customer_id=body.customer_id,
            order_id=body.order_id,
            message=body.message,
        )

    except AIServiceConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    except AIServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    except CustomerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except OrderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except InvalidRefundAmountError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return RefundRequestResponse.model_validate(refund_request)
