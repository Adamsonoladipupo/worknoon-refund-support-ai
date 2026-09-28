"""
Deterministic refund policy engine.

Completely independent of FastAPI, SQLAlchemy sessions, repositories, and the LLM.
All inputs are plain Python values; no database access is performed here.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

REFUND_WINDOW_DAYS: int = 30
HIGH_VALUE_THRESHOLD: Decimal = Decimal("500.00")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RefundDecision(str, Enum):
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    ESCALATED = "ESCALATED"


class RefundRule(str, Enum):
    ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
    CUSTOMER_MISMATCH = "CUSTOMER_MISMATCH"
    ORDER_TOO_OLD = "ORDER_TOO_OLD"
    FINAL_SALE_ITEM = "FINAL_SALE_ITEM"
    HIGH_VALUE_REFUND = "HIGH_VALUE_REFUND"
    DAMAGED_ITEM = "DAMAGED_ITEM"
    INCORRECT_ITEM = "INCORRECT_ITEM"
    STANDARD_REFUND = "STANDARD_REFUND"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RefundPolicyResult:
    """Immutable result produced by RefundPolicy.evaluate()."""

    decision: RefundDecision
    rule: RefundRule
    reason: str


# ---------------------------------------------------------------------------
# Input structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OrderItemFact:
    """Minimal facts about a single order item needed for policy evaluation."""

    item_id: uuid.UUID
    product_name: str
    final_sale: bool


@dataclass(frozen=True)
class OrderFact:
    """Minimal facts about an order needed for policy evaluation."""

    order_id: uuid.UUID
    customer_id: uuid.UUID
    order_date: datetime  # must be timezone-aware
    total_amount: Decimal
    items: tuple[OrderItemFact, ...]


# ---------------------------------------------------------------------------
# Refund reason categories (used by the caller to signal intent)
# ---------------------------------------------------------------------------


class RefundReason(str, Enum):
    DAMAGED_ITEM = "DAMAGED_ITEM"
    INCORRECT_ITEM = "INCORRECT_ITEM"
    OTHER = "OTHER"


# ---------------------------------------------------------------------------
# Policy engine
# ---------------------------------------------------------------------------


class RefundPolicy:
    """
    Deterministic refund policy engine.

    Usage::

        policy = RefundPolicy()
        result = policy.evaluate(
            requesting_customer_id=customer.id,
            order=order_fact,          # OrderFact or None
            requested_item_id=item_id, # uuid.UUID of the item to refund
            requested_amount=Decimal("49.99"),
            refund_reason=RefundReason.DAMAGED_ITEM,
            now=datetime.now(timezone.utc),  # optional, defaults to UTC now
        )

    The ``now`` parameter exists so tests can inject a fixed reference time
    without patching.
    """

    def evaluate(
        self,
        *,
        requesting_customer_id: uuid.UUID,
        order: Optional[OrderFact],
        requested_item_id: uuid.UUID,
        requested_amount: Decimal,
        refund_reason: RefundReason,
        now: Optional[datetime] = None,
    ) -> RefundPolicyResult:
        """
        Evaluate the refund request and return a deterministic RefundPolicyResult.

        Precedence (first matching rule wins):
          1. Order/customer validity  → ORDER_NOT_FOUND, CUSTOMER_MISMATCH
          2. Order age                → ORDER_TOO_OLD
          3. Final-sale item          → FINAL_SALE_ITEM
          4. High-value refund        → HIGH_VALUE_REFUND  (escalated)
          5. Damaged/incorrect item   → DAMAGED_ITEM, INCORRECT_ITEM
          6. Standard eligible refund → STANDARD_REFUND
        """
        if now is None:
            now = datetime.now(timezone.utc)

        # Ensure ``now`` is timezone-aware so comparisons with order_date work.
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        # ------------------------------------------------------------------
        # 1. Order/customer validity
        # ------------------------------------------------------------------
        if order is None:
            return RefundPolicyResult(
                decision=RefundDecision.DENIED,
                rule=RefundRule.ORDER_NOT_FOUND,
                reason="The requested order could not be found.",
            )

        if order.customer_id != requesting_customer_id:
            return RefundPolicyResult(
                decision=RefundDecision.DENIED,
                rule=RefundRule.CUSTOMER_MISMATCH,
                reason="This order does not belong to the requesting customer.",
            )

        # ------------------------------------------------------------------
        # 2. Order age
        # ------------------------------------------------------------------
        order_date = order.order_date
        if order_date.tzinfo is None:
            order_date = order_date.replace(tzinfo=timezone.utc)

        age_days = (now - order_date).days
        if age_days > REFUND_WINDOW_DAYS:
            return RefundPolicyResult(
                decision=RefundDecision.DENIED,
                rule=RefundRule.ORDER_TOO_OLD,
                reason=(
                    f"The order is {age_days} days old; refunds are only accepted "
                    f"within {REFUND_WINDOW_DAYS} days of the order date."
                ),
            )

        # ------------------------------------------------------------------
        # 3. Final-sale item
        # ------------------------------------------------------------------
        item = next(
            (i for i in order.items if i.item_id == requested_item_id), None
        )
        if item is not None and item.final_sale:
            return RefundPolicyResult(
                decision=RefundDecision.DENIED,
                rule=RefundRule.FINAL_SALE_ITEM,
                reason=(
                    f'"{item.product_name}" is a final-sale item and cannot be refunded.'
                ),
            )

        # ------------------------------------------------------------------
        # 4. High-value refund  (> threshold → escalate, = threshold → continue)
        # ------------------------------------------------------------------
        if requested_amount > HIGH_VALUE_THRESHOLD:
            return RefundPolicyResult(
                decision=RefundDecision.ESCALATED,
                rule=RefundRule.HIGH_VALUE_REFUND,
                reason=(
                    f"The requested refund amount of ${requested_amount} exceeds "
                    f"${HIGH_VALUE_THRESHOLD} and requires manual review."
                ),
            )

        # ------------------------------------------------------------------
        # 5. Damaged / incorrect item
        # ------------------------------------------------------------------
        if refund_reason == RefundReason.DAMAGED_ITEM:
            return RefundPolicyResult(
                decision=RefundDecision.APPROVED,
                rule=RefundRule.DAMAGED_ITEM,
                reason="Refund approved: item was reported as damaged.",
            )

        if refund_reason == RefundReason.INCORRECT_ITEM:
            return RefundPolicyResult(
                decision=RefundDecision.APPROVED,
                rule=RefundRule.INCORRECT_ITEM,
                reason="Refund approved: an incorrect item was received.",
            )

        # ------------------------------------------------------------------
        # 6. Standard eligible refund
        # ------------------------------------------------------------------
        return RefundPolicyResult(
            decision=RefundDecision.APPROVED,
            rule=RefundRule.STANDARD_REFUND,
            reason="Refund approved: order is within the refund window.",
        )
