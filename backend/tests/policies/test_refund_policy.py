"""
Unit tests for the deterministic refund policy engine.

Covers all 10 required cases:
  1.  Missing order                          → DENIED / ORDER_NOT_FOUND
  2.  Customer mismatch                      → DENIED / CUSTOMER_MISMATCH
  3.  Order older than 30 days               → DENIED / ORDER_TOO_OLD
  4.  Final-sale item                        → DENIED / FINAL_SALE_ITEM
  5.  Amount exactly $500                    → APPROVED (not escalated; > threshold required)
  6.  Amount greater than $500               → ESCALATED / HIGH_VALUE_REFUND
  7.  Damaged item                           → APPROVED / DAMAGED_ITEM
  8.  Incorrect item                         → APPROVED / INCORRECT_ITEM
  9.  Standard eligible refund               → APPROVED / STANDARD_REFUND
  10. High-value old order (precedence test) → DENIED / ORDER_TOO_OLD (not HIGH_VALUE_REFUND)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.policies.refund_policy import (
    OrderFact,
    OrderItemFact,
    RefundDecision,
    RefundPolicy,
    RefundReason,
    RefundRule,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

POLICY = RefundPolicy()

# A fixed "now" used across all tests for reproducibility.
NOW = datetime(2026, 9, 25, 21, 0, 0, tzinfo=timezone.utc)

CUSTOMER_ID = uuid.uuid4()
OTHER_CUSTOMER_ID = uuid.uuid4()
ORDER_ID = uuid.uuid4()
ITEM_ID = uuid.uuid4()
FINAL_SALE_ITEM_ID = uuid.uuid4()


def _order_date(days_ago: int) -> datetime:
    """Return a timezone-aware order date *days_ago* days before NOW."""
    return NOW - timedelta(days=days_ago)


def _make_order(
    *,
    customer_id: uuid.UUID = CUSTOMER_ID,
    days_ago: int = 5,
    total_amount: Decimal = Decimal("49.99"),
    items: tuple[OrderItemFact, ...] | None = None,
) -> OrderFact:
    if items is None:
        items = (
            OrderItemFact(item_id=ITEM_ID, product_name="Widget", final_sale=False),
        )
    return OrderFact(
        order_id=ORDER_ID,
        customer_id=customer_id,
        order_date=_order_date(days_ago),
        total_amount=total_amount,
        items=items,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRefundPolicy:
    # --- 1. Missing order ---------------------------------------------------

    def test_missing_order_is_denied(self) -> None:
        result = POLICY.evaluate(
            requesting_customer_id=CUSTOMER_ID,
            order=None,
            requested_item_id=ITEM_ID,
            requested_amount=Decimal("10.00"),
            refund_reason=RefundReason.OTHER,
            now=NOW,
        )
        assert result.decision == RefundDecision.DENIED
        assert result.rule == RefundRule.ORDER_NOT_FOUND

    # --- 2. Customer mismatch -----------------------------------------------

    def test_customer_mismatch_is_denied(self) -> None:
        order = _make_order(customer_id=OTHER_CUSTOMER_ID)
        result = POLICY.evaluate(
            requesting_customer_id=CUSTOMER_ID,
            order=order,
            requested_item_id=ITEM_ID,
            requested_amount=Decimal("10.00"),
            refund_reason=RefundReason.OTHER,
            now=NOW,
        )
        assert result.decision == RefundDecision.DENIED
        assert result.rule == RefundRule.CUSTOMER_MISMATCH

    # --- 3. Order older than 30 days ----------------------------------------

    def test_order_too_old_is_denied(self) -> None:
        order = _make_order(days_ago=31)
        result = POLICY.evaluate(
            requesting_customer_id=CUSTOMER_ID,
            order=order,
            requested_item_id=ITEM_ID,
            requested_amount=Decimal("10.00"),
            refund_reason=RefundReason.OTHER,
            now=NOW,
        )
        assert result.decision == RefundDecision.DENIED
        assert result.rule == RefundRule.ORDER_TOO_OLD

    # --- 4. Final-sale item -------------------------------------------------

    def test_final_sale_item_is_denied(self) -> None:
        order = _make_order(
            items=(
                OrderItemFact(
                    item_id=FINAL_SALE_ITEM_ID,
                    product_name="Clearance Tee",
                    final_sale=True,
                ),
            )
        )
        result = POLICY.evaluate(
            requesting_customer_id=CUSTOMER_ID,
            order=order,
            requested_item_id=FINAL_SALE_ITEM_ID,
            requested_amount=Decimal("9.99"),
            refund_reason=RefundReason.OTHER,
            now=NOW,
        )
        assert result.decision == RefundDecision.DENIED
        assert result.rule == RefundRule.FINAL_SALE_ITEM

    # --- 5. Amount exactly $500 — NOT escalated (threshold is *strictly* >) -

    def test_amount_exactly_500_is_not_escalated(self) -> None:
        order = _make_order()
        result = POLICY.evaluate(
            requesting_customer_id=CUSTOMER_ID,
            order=order,
            requested_item_id=ITEM_ID,
            requested_amount=Decimal("500.00"),
            refund_reason=RefundReason.OTHER,
            now=NOW,
        )
        # $500.00 is not *greater than* the threshold, so it should not escalate.
        assert result.decision == RefundDecision.APPROVED
        assert result.rule == RefundRule.STANDARD_REFUND

    # --- 6. Amount greater than $500 ----------------------------------------

    def test_amount_above_500_is_escalated(self) -> None:
        order = _make_order()
        result = POLICY.evaluate(
            requesting_customer_id=CUSTOMER_ID,
            order=order,
            requested_item_id=ITEM_ID,
            requested_amount=Decimal("500.01"),
            refund_reason=RefundReason.OTHER,
            now=NOW,
        )
        assert result.decision == RefundDecision.ESCALATED
        assert result.rule == RefundRule.HIGH_VALUE_REFUND

    # --- 7. Damaged item ----------------------------------------------------

    def test_damaged_item_is_approved(self) -> None:
        order = _make_order()
        result = POLICY.evaluate(
            requesting_customer_id=CUSTOMER_ID,
            order=order,
            requested_item_id=ITEM_ID,
            requested_amount=Decimal("49.99"),
            refund_reason=RefundReason.DAMAGED_ITEM,
            now=NOW,
        )
        assert result.decision == RefundDecision.APPROVED
        assert result.rule == RefundRule.DAMAGED_ITEM

    # --- 8. Incorrect item --------------------------------------------------

    def test_incorrect_item_is_approved(self) -> None:
        order = _make_order()
        result = POLICY.evaluate(
            requesting_customer_id=CUSTOMER_ID,
            order=order,
            requested_item_id=ITEM_ID,
            requested_amount=Decimal("49.99"),
            refund_reason=RefundReason.INCORRECT_ITEM,
            now=NOW,
        )
        assert result.decision == RefundDecision.APPROVED
        assert result.rule == RefundRule.INCORRECT_ITEM

    # --- 9. Standard eligible refund ----------------------------------------

    def test_standard_eligible_refund_is_approved(self) -> None:
        order = _make_order()
        result = POLICY.evaluate(
            requesting_customer_id=CUSTOMER_ID,
            order=order,
            requested_item_id=ITEM_ID,
            requested_amount=Decimal("49.99"),
            refund_reason=RefundReason.OTHER,
            now=NOW,
        )
        assert result.decision == RefundDecision.APPROVED
        assert result.rule == RefundRule.STANDARD_REFUND

    # --- 10. Precedence: ORDER_TOO_OLD beats HIGH_VALUE_REFUND --------------

    def test_order_too_old_takes_precedence_over_high_value(self) -> None:
        """
        An order that is both too old AND high-value must be denied for
        ORDER_TOO_OLD, not escalated for HIGH_VALUE_REFUND.
        This verifies that age check (step 2) runs before the value check (step 4).
        """
        order = _make_order(days_ago=45)  # well outside the 30-day window
        result = POLICY.evaluate(
            requesting_customer_id=CUSTOMER_ID,
            order=order,
            requested_item_id=ITEM_ID,
            requested_amount=Decimal("999.00"),  # would trigger HIGH_VALUE_REFUND
            refund_reason=RefundReason.OTHER,
            now=NOW,
        )
        assert result.decision == RefundDecision.DENIED
        assert result.rule == RefundRule.ORDER_TOO_OLD
