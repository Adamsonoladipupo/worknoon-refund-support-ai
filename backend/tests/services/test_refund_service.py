"""
Unit tests for RefundService.

The service is fully isolated from the database: all three repositories are
mocked with AsyncMock so no real AsyncSession or DB connection is needed.

ORM models are represented by SimpleNamespace objects — plain attribute bags
that satisfy attribute reads without any SQLAlchemy instrumentation.

The real RefundPolicy is *not* mocked — we want to verify that the service
wires it correctly and that the resulting decision is persisted on the record.

Tests:
  1.  Customer not found                      → CustomerNotFoundError
  2.  Order not found                         → OrderNotFoundError
  3.  Customer/order mismatch                 → OrderNotFoundError
  4.  Zero requested amount                   → InvalidRefundAmountError
  5.  Negative requested amount               → InvalidRefundAmountError
  6.  Requested amount > order total          → InvalidRefundAmountError
  7.  Successful approved refund              → RefundRequest.decision == "APPROVED"
  8.  Denied refund from policy               → RefundRequest.decision == "DENIED"
  9.  Escalated refund from policy            → RefundRequest.decision == "ESCALATED"
  10. RefundRequest persisted with decision   → repo.create called with correct fields
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import (
    CustomerNotFoundError,
    InvalidRefundAmountError,
    OrderNotFoundError,
)
from app.models.refund_request import RefundRequest
from app.policies.refund_policy import RefundReason
from app.services.refund_service import RefundService

# ---------------------------------------------------------------------------
# Stable IDs shared across tests
# ---------------------------------------------------------------------------

CUSTOMER_ID = uuid.uuid4()
OTHER_CUSTOMER_ID = uuid.uuid4()
ORDER_ID = uuid.uuid4()
ITEM_ID = uuid.uuid4()

NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Stand-in factories using SimpleNamespace
# (Bypasses SQLAlchemy instrumentation — pure attribute bags)
# ---------------------------------------------------------------------------


def _make_customer(customer_id: uuid.UUID = CUSTOMER_ID) -> SimpleNamespace:
    return SimpleNamespace(
        id=customer_id,
        name="Alice",
        email="alice@example.com",
    )


def _make_item(
    *,
    item_id: uuid.UUID = ITEM_ID,
    final_sale: bool = False,
    unit_price: Decimal = Decimal("49.99"),
) -> SimpleNamespace:
    return SimpleNamespace(
        id=item_id,
        order_id=ORDER_ID,
        product_name="Widget",
        quantity=1,
        unit_price=unit_price,
        final_sale=final_sale,
    )


def _make_order(
    *,
    customer_id: uuid.UUID = CUSTOMER_ID,
    total_amount: Decimal = Decimal("49.99"),
    days_old: int = 5,
    items: list | None = None,
) -> SimpleNamespace:
    if items is None:
        items = [_make_item(unit_price=total_amount)]
    return SimpleNamespace(
        id=ORDER_ID,
        customer_id=customer_id,
        order_number="ORD-001",
        order_date=NOW - timedelta(days=days_old),
        total_amount=total_amount,
        status="completed",
        items=items,
    )


def _make_service(
    *,
    customer: SimpleNamespace | None = None,
    order: SimpleNamespace | None = None,
):
    """
    Return (service, mock_session, mock_customer_repo, mock_order_repo, mock_refund_repo).

    Patches CustomerRepository, OrderRepository, and RefundRepository so the
    service never touches a real database session.
    """
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_customer_repo = AsyncMock()
    mock_customer_repo.get_by_id = AsyncMock(return_value=customer)

    mock_order_repo = AsyncMock()
    mock_order_repo.get_by_id = AsyncMock(return_value=order)

    # Default: echo back the RefundRequest with an id stamped on.
    async def _echo_create(rr: RefundRequest) -> RefundRequest:
        rr.id = uuid.uuid4()
        rr.created_at = NOW
        rr.updated_at = NOW
        return rr

    mock_refund_repo = AsyncMock()
    mock_refund_repo.create = _echo_create

    with (
        patch(
            "app.services.refund_service.CustomerRepository",
            return_value=mock_customer_repo,
        ),
        patch(
            "app.services.refund_service.OrderRepository",
            return_value=mock_order_repo,
        ),
        patch(
            "app.services.refund_service.RefundRepository",
            return_value=mock_refund_repo,
        ),
    ):
        service = RefundService(mock_session)

    # Expose repos so individual tests can override create() if needed.
    service._customer_repo = mock_customer_repo  # type: ignore[attr-defined]
    service._order_repo = mock_order_repo  # type: ignore[attr-defined]
    service._refund_repo = mock_refund_repo  # type: ignore[attr-defined]
    service._mock_session = mock_session  # type: ignore[attr-defined]

    return service


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRefundService:

    # --- 1. Customer not found ---------------------------------------------

    async def test_customer_not_found_raises(self) -> None:
        service = _make_service(customer=None, order=_make_order())
        with pytest.raises(CustomerNotFoundError):
            await service.process_refund(
                customer_id=CUSTOMER_ID,
                order_id=ORDER_ID,
                requested_amount=Decimal("10.00"),
                reason=RefundReason.OTHER,
            )

    # --- 2. Order not found ------------------------------------------------

    async def test_order_not_found_raises(self) -> None:
        service = _make_service(customer=_make_customer(), order=None)
        with pytest.raises(OrderNotFoundError):
            await service.process_refund(
                customer_id=CUSTOMER_ID,
                order_id=ORDER_ID,
                requested_amount=Decimal("10.00"),
                reason=RefundReason.OTHER,
            )

    # --- 3. Customer/order mismatch ----------------------------------------

    async def test_customer_order_mismatch_raises(self) -> None:
        order = _make_order(customer_id=OTHER_CUSTOMER_ID)
        service = _make_service(customer=_make_customer(), order=order)
        with pytest.raises(OrderNotFoundError):
            await service.process_refund(
                customer_id=CUSTOMER_ID,
                order_id=ORDER_ID,
                requested_amount=Decimal("10.00"),
                reason=RefundReason.OTHER,
            )

    # --- 4. Zero requested amount ------------------------------------------

    async def test_zero_amount_raises(self) -> None:
        service = _make_service(customer=_make_customer(), order=_make_order())
        with pytest.raises(InvalidRefundAmountError):
            await service.process_refund(
                customer_id=CUSTOMER_ID,
                order_id=ORDER_ID,
                requested_amount=Decimal("0"),
                reason=RefundReason.OTHER,
            )

    # --- 5. Negative requested amount --------------------------------------

    async def test_negative_amount_raises(self) -> None:
        service = _make_service(customer=_make_customer(), order=_make_order())
        with pytest.raises(InvalidRefundAmountError):
            await service.process_refund(
                customer_id=CUSTOMER_ID,
                order_id=ORDER_ID,
                requested_amount=Decimal("-1.00"),
                reason=RefundReason.OTHER,
            )

    # --- 6. Amount exceeds order total -------------------------------------

    async def test_amount_exceeds_order_total_raises(self) -> None:
        order = _make_order(total_amount=Decimal("49.99"))
        service = _make_service(customer=_make_customer(), order=order)
        with pytest.raises(InvalidRefundAmountError):
            await service.process_refund(
                customer_id=CUSTOMER_ID,
                order_id=ORDER_ID,
                requested_amount=Decimal("50.00"),
                reason=RefundReason.OTHER,
            )

    # --- 7. Successful approved refund -------------------------------------

    async def test_approved_refund_returns_record(self) -> None:
        order = _make_order(total_amount=Decimal("49.99"), days_old=5)
        service = _make_service(customer=_make_customer(), order=order)
        result = await service.process_refund(
            customer_id=CUSTOMER_ID,
            order_id=ORDER_ID,
            requested_amount=Decimal("49.99"),
            reason=RefundReason.OTHER,
        )
        assert result.decision == "APPROVED"
        service._mock_session.commit.assert_awaited_once()

    # --- 8. Denied refund from policy (order too old) ----------------------

    async def test_denied_refund_order_too_old(self) -> None:
        order = _make_order(total_amount=Decimal("49.99"), days_old=45)
        service = _make_service(customer=_make_customer(), order=order)
        result = await service.process_refund(
            customer_id=CUSTOMER_ID,
            order_id=ORDER_ID,
            requested_amount=Decimal("49.99"),
            reason=RefundReason.OTHER,
        )
        assert result.decision == "DENIED"

    # --- 9. Escalated refund from policy (high-value) ----------------------

    async def test_escalated_refund_high_value(self) -> None:
        order = _make_order(total_amount=Decimal("999.00"), days_old=5)
        service = _make_service(customer=_make_customer(), order=order)
        result = await service.process_refund(
            customer_id=CUSTOMER_ID,
            order_id=ORDER_ID,
            requested_amount=Decimal("501.00"),
            reason=RefundReason.OTHER,
        )
        assert result.decision == "ESCALATED"

    # --- 10. RefundRequest persisted with correct decision fields ----------

    async def test_refund_request_persisted_with_policy_decision(self) -> None:
        """The RefundRequest handed to the repository must carry the policy
        decision and reason — not null/default values."""
        order = _make_order(total_amount=Decimal("49.99"), days_old=2)
        service = _make_service(customer=_make_customer(), order=order)

        captured: list[RefundRequest] = []

        async def _capturing_create(rr: RefundRequest) -> RefundRequest:
            captured.append(rr)
            rr.id = uuid.uuid4()
            rr.created_at = NOW
            rr.updated_at = NOW
            return rr

        service._refund_repo.create = _capturing_create

        await service.process_refund(
            customer_id=CUSTOMER_ID,
            order_id=ORDER_ID,
            requested_amount=Decimal("49.99"),
            reason=RefundReason.DAMAGED_ITEM,
        )

        assert len(captured) == 1
        rr = captured[0]
        assert rr.customer_id == CUSTOMER_ID
        assert rr.order_id == ORDER_ID
        assert rr.requested_amount == Decimal("49.99")
        assert rr.reason == RefundReason.DAMAGED_ITEM.value
        # Policy: DAMAGED_ITEM within window → APPROVED / DAMAGED_ITEM
        assert rr.decision == "APPROVED"
        assert rr.decision_reason is not None and len(rr.decision_reason) > 0
        service._mock_session.commit.assert_awaited_once()
