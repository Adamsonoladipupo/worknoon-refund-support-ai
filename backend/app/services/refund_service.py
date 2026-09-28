
"""
Refund Request Service.

Owns the end-to-end application workflow for processing a refund request.

There are two workflows:

1. process_refund()
   Direct structured refund processing.
   The caller already provides the refund reason and amount.

2. process_ai_refund()
   Natural-language refund processing.
   Gemini extracts the refund reason and requested amount from the customer's
   message. The extracted information is then passed into process_refund(),
   where the deterministic RefundPolicy remains the final authority.

Important architecture rule:
    Gemini does NOT decide whether a refund is approved, denied, or escalated.

    Gemini:
        Customer message
            ↓
        Structured extraction
            ↓
        reason + requested_amount

    RefundPolicy:
        reason + amount + order facts
            ↓
        APPROVED / DENIED / ESCALATED

The AI layer therefore assists with understanding the customer's message,
while the deterministic policy engine remains authoritative.
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


# One deterministic policy instance is shared by the service.
_policy = RefundPolicy()


class RefundService:
    """Application service for processing refund requests."""

    def __init__(
            self,
            session: AsyncSession,
            ai_service: AIService | None = None,
    ) -> None:
        """
        Initialise the refund service.

        Args:
            session:
                SQLAlchemy async database session.

            ai_service:
                Optional AIService used by process_ai_refund().

                It is optional so the existing deterministic refund workflow
                remains usable without Gemini.
        """
        self._session = session
        self._customer_repo = CustomerRepository(session)
        self._order_repo = OrderRepository(session)
        self._refund_repo = RefundRepository(session)
        self._ai_service = ai_service

    # ======================================================================
    # DIRECT / STRUCTURED REFUND WORKFLOW
    # ======================================================================

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

        Workflow:

            1. Fetch customer.
            2. Fetch order.
            3. Validate customer ownership.
            4. Validate requested amount.
            5. Convert ORM data into plain policy facts.
            6. Evaluate deterministic RefundPolicy.
            7. Persist RefundRequest.
            8. Commit transaction.

        The policy engine is the sole authority for the refund decision.

        Raises:
            CustomerNotFoundError:
                If no customer exists with customer_id.

            OrderNotFoundError:
                If no order exists with order_id, or the order does not
                belong to the requesting customer.

            InvalidRefundAmountError:
                If requested_amount is zero/negative or exceeds the order
                total.
        """

        # ------------------------------------------------------------------
        # 1. Fetch customer
        # ------------------------------------------------------------------
        customer = await self._customer_repo.get_by_id(customer_id)

        if customer is None:
            raise CustomerNotFoundError(customer_id)

        # ------------------------------------------------------------------
        # 2. Fetch order
        #
        # OrderRepository.get_by_id() eager-loads the order items, so
        # accessing order.items below does not trigger an unexpected
        # asynchronous lazy-load.
        # ------------------------------------------------------------------
        order = await self._order_repo.get_by_id(order_id)

        if order is None:
            raise OrderNotFoundError(order_id)

        # ------------------------------------------------------------------
        # 3. Validate ownership
        #
        # We intentionally return OrderNotFoundError rather than exposing
        # that an order exists for another customer.
        # ------------------------------------------------------------------
        if order.customer_id != customer_id:
            raise OrderNotFoundError(order_id)

        # ------------------------------------------------------------------
        # 4. Validate requested amount
        # ------------------------------------------------------------------
        if requested_amount <= Decimal("0"):
            raise InvalidRefundAmountError(
                f"Requested refund amount must be positive, "
                f"got {requested_amount}.",
                amount=requested_amount,
            )

        if requested_amount > order.total_amount:
            raise InvalidRefundAmountError(
                f"Requested refund amount {requested_amount} exceeds "
                f"the order total {order.total_amount}.",
                amount=requested_amount,
            )

        # ------------------------------------------------------------------
        # 5. Convert ORM entities into plain policy facts
        #
        # The policy layer should not depend on SQLAlchemy ORM models.
        # ------------------------------------------------------------------
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

        # ------------------------------------------------------------------
        # 6. Determine the item being evaluated
        #
        # The current API represents a refund request at order level rather
        # than accepting an explicit item_id.
        #
        # Therefore, for the current MVP, the first order item is treated
        # as the focal item.
        #
        # A future item-level refund API can extend process_refund() with
        # an explicit item_id.
        # ------------------------------------------------------------------
        first_item_id = (
            item_facts[0].item_id
            if item_facts
            else uuid.uuid4()
        )

        # ------------------------------------------------------------------
        # 7. Evaluate deterministic refund policy
        #
        # IMPORTANT:
        # Gemini is NOT involved here.
        #
        # RefundPolicy remains the authority for:
        #     APPROVED
        #     DENIED
        #     ESCALATED
        # ------------------------------------------------------------------
        policy_result = _policy.evaluate(
            requesting_customer_id=customer_id,
            order=order_fact,
            requested_item_id=first_item_id,
            requested_amount=requested_amount,
            refund_reason=reason,
        )

        # ------------------------------------------------------------------
        # 8. Create persistence model
        # ------------------------------------------------------------------
        refund_request = RefundRequest(
            customer_id=customer_id,
            order_id=order_id,
            reason=reason.value,
            requested_amount=requested_amount,
            decision=policy_result.decision.value,
            decision_reason=policy_result.reason,
        )

        # ------------------------------------------------------------------
        # 9. Persist refund request
        # ------------------------------------------------------------------
        refund_request = await self._refund_repo.create(refund_request)

        # ------------------------------------------------------------------
        # 10. Commit transaction
        # ------------------------------------------------------------------
        await self._session.commit()

        return refund_request

    # ======================================================================
    # AI / NATURAL-LANGUAGE REFUND WORKFLOW
    # ======================================================================

    async def process_ai_refund(
            self,
            *,
            customer_id: uuid.UUID,
            order_id: uuid.UUID,
            message: str,
    ) -> RefundRequest:
        """
        Process a natural-language customer refund request.

        Workflow:

            Customer message
                    ↓
                Gemini AI
                    ↓
            RefundRequestAnalysis
                    ↓
             reason + amount
                    ↓
            process_refund()
                    ↓
             RefundPolicy
                    ↓
        APPROVED / DENIED / ESCALATED

        Gemini is only responsible for extracting structured information
        from the customer's message.

        It does NOT make the final refund decision.

        Args:
            customer_id:
                ID of the customer making the request.

            order_id:
                ID of the order being refunded.

            message:
                Natural-language refund request from the customer.

        Returns:
            Persisted RefundRequest containing the deterministic policy result.

        Raises:
            AIServiceError:
                If AIService has not been configured or Gemini fails.

            InvalidRefundAmountError:
                If Gemini cannot extract a valid refund amount.

            CustomerNotFoundError:
                If the customer does not exist.

            OrderNotFoundError:
                If the order does not exist or belongs to another customer.

            InvalidRefundAmountError:
                If the extracted amount is invalid or exceeds the order total.
        """

        # ------------------------------------------------------------------
        # 1. Ensure AI service is configured
        # ------------------------------------------------------------------
        if self._ai_service is None:
            raise AIServiceError(
                "AI service is not configured for this refund workflow."
            )

        # ------------------------------------------------------------------
        # 2. Send the customer's natural-language message to Gemini
        #
        # Gemini returns a RefundRequestAnalysis containing:
        #
        #     reason
        #     summary
        #     requested_amount
        #     confidence
        #
        # Gemini does NOT determine APPROVED / DENIED / ESCALATED.
        # ------------------------------------------------------------------
        analysis = await self._ai_service.analyze_request(message)

        # ------------------------------------------------------------------
        # 3. Require an explicit amount
        #
        # We deliberately do not allow the AI to invent an amount.
        # ------------------------------------------------------------------
        if analysis.requested_amount is None:
            raise InvalidRefundAmountError(
                "The customer message did not contain a valid "
                "refund amount."
            )

        # ------------------------------------------------------------------
        # 4. Convert the AI reason into the deterministic policy enum
        #
        # Both enums currently contain:
        #
        #     DAMAGED_ITEM
        #     INCORRECT_ITEM
        #     OTHER
        #
        # They remain separate bounded contexts intentionally.
        # ------------------------------------------------------------------
        policy_reason = RefundReason(analysis.reason.value)

        # ------------------------------------------------------------------
        # 5. Pass the extracted information into the normal refund workflow
        #
        # From this point onward, Gemini is completely out of the decision
        # process.
        #
        # process_refund() will:
        #
        #     - fetch the customer
        #     - fetch the order
        #     - validate ownership
        #     - validate amount
        #     - evaluate RefundPolicy
        #     - persist the result
        # ------------------------------------------------------------------
        return await self.process_refund(
            customer_id=customer_id,
            order_id=order_id,
            requested_amount=analysis.requested_amount,
            reason=policy_reason,
        )
