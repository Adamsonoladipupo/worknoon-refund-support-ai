"""
Refund request service.

Two workflows:
  process_refund()     — direct structured refund; caller supplies reason + amount.
  process_ai_refund()  — natural-language refund; Gemini extracts reason + amount,
                         then process_refund() runs the deterministic policy.

Architecture rule: Gemini does NOT decide APPROVED / DENIED / ESCALATED.
RefundPolicy is the sole authority for all decisions.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.exceptions import AIServiceError
from app.ai.service import AIService
from app.core.exceptions import (
    CustomerNotFoundError,
    InvalidRefundAmountError,
    OrderNotFoundError,
)
from app.models.refund_request import RefundRequest
from app.policies.refund_policy import (
    OrderFact,
    OrderItemFact,
    RefundPolicy,
    RefundReason,
)
from app.repositories.customer_repository import CustomerRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.refund_repository import RefundRepository


_policy = RefundPolicy()


class RefundService:
    """Application service for processing refund requests."""

    def __init__(
            self,
            session: AsyncSession,
            ai_service: AIService | None = None,
    ) -> None:
        """
        Args:
            session: SQLAlchemy async database session.
            ai_service: Optional AIService used by process_ai_refund().
                        Omitting it keeps the structured refund workflow usable
                        without Gemini.
        """
        self._session = session
        self._customer_repo = CustomerRepository(session)
        self._order_repo = OrderRepository(session)
        self._refund_repo = RefundRepository(session)
        self._ai_service = ai_service

    async def process_refund(
            self,
            *,
            customer_id: uuid.UUID,
            order_id: uuid.UUID,
            requested_amount: Decimal,
            reason: RefundReason,
    ) -> RefundRequest:
        """
        Process a structured refund request end-to-end.

        Raises:
            CustomerNotFoundError: customer_id does not exist.
            OrderNotFoundError: order_id does not exist or belongs to another customer.
            InvalidRefundAmountError: amount is zero/negative or exceeds the order total.
        """
        customer = await self._customer_repo.get_by_id(customer_id)
        if customer is None:
            raise CustomerNotFoundError(customer_id)

        # OrderRepository.get_by_id() eager-loads items so order.items is safe to access.
        order = await self._order_repo.get_by_id(order_id)
        if order is None:
            raise OrderNotFoundError(order_id)

        # Return OrderNotFoundError for mismatches — avoids exposing that an order
        # exists for a different customer.
        if order.customer_id != customer_id:
            raise OrderNotFoundError(order_id)

        if requested_amount <= Decimal("0"):
            raise InvalidRefundAmountError(
                f"Requested refund amount must be positive, got {requested_amount}.",
                amount=requested_amount,
            )

        if requested_amount > order.total_amount:
            raise InvalidRefundAmountError(
                f"Requested refund amount {requested_amount} exceeds "
                f"the order total {order.total_amount}.",
                amount=requested_amount,
            )

        item_facts = tuple(
            OrderItemFact(
                item_id=item.id,
                product_name=item.product_name,
                final_sale=item.final_sale,
            )
            for item in order.items
        )

        order_fact = OrderFact(
            order_id=order.id,
            customer_id=order.customer_id,
            order_date=order.order_date,
            total_amount=order.total_amount,
            items=item_facts,
        )

        # MVP: refunds are at order level, not item level. Use the first item as
        # the focal item. A future item-level API can pass an explicit item_id.
        first_item_id = item_facts[0].item_id if item_facts else uuid.uuid4()

        policy_result = _policy.evaluate(
            requesting_customer_id=customer_id,
            order=order_fact,
            requested_item_id=first_item_id,
            requested_amount=requested_amount,
            refund_reason=reason,
        )

        refund_request = RefundRequest(
            customer_id=customer_id,
            order_id=order_id,
            reason=reason.value,
            requested_amount=requested_amount,
            decision=policy_result.decision.value,
            decision_reason=policy_result.reason,
        )

        refund_request = await self._refund_repo.create(refund_request)
        await self._session.commit()

        return refund_request

    async def process_ai_refund(
            self,
            *,
            customer_id: uuid.UUID,
            order_id: uuid.UUID,
            message: str,
    ) -> RefundRequest:
        """
        Process a natural-language customer refund request.

        Gemini extracts reason + amount from the message, then process_refund()
        applies the deterministic policy. Gemini does NOT make the final decision.

        Raises:
            AIServiceError: AIService is not configured or Gemini fails.
            InvalidRefundAmountError: Gemini could not extract a valid amount.
            CustomerNotFoundError / OrderNotFoundError: see process_refund().
        """
        if self._ai_service is None:
            raise AIServiceError(
                "AI service is not configured for this refund workflow."
            )

        analysis = await self._ai_service.analyze_request(message)

        # Do not allow the AI to invent an amount — the customer must state it explicitly.
        if analysis.requested_amount is None:
            raise InvalidRefundAmountError(
                "The customer message did not contain a valid refund amount."
            )

        # Both RefundReason enums share the same values (DAMAGED_ITEM / INCORRECT_ITEM /
        # OTHER) but are kept in separate bounded contexts intentionally.
        policy_reason = RefundReason(analysis.reason.value)

        return await self.process_refund(
            customer_id=customer_id,
            order_id=order_id,
            requested_amount=analysis.requested_amount,
            reason=policy_reason,
        )
