import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.refund_request import RefundRequest


class RefundRepository:
    """All database operations for the RefundRequest model."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, refund_request: RefundRequest) -> RefundRequest:
        """Persist a new RefundRequest and flush so the DB-generated fields
        (created_at, updated_at) are populated on the returned object.

        The caller is responsible for committing the transaction.
        """
        self._session.add(refund_request)
        await self._session.flush()
        await self._session.refresh(refund_request)
        return refund_request

    async def get_by_id(self, refund_id: uuid.UUID) -> RefundRequest | None:
        result = await self._session.execute(
            select(RefundRequest).where(RefundRequest.id == refund_id)
        )
        return result.scalar_one_or_none()

    async def get_by_order_id(self, order_id: uuid.UUID) -> list[RefundRequest]:
        result = await self._session.execute(
            select(RefundRequest)
            .where(RefundRequest.order_id == order_id)
            .order_by(RefundRequest.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_recent(self, limit: int = 50) -> list[RefundRequest]:
        """Return the most recent refund requests, newest first.

        Eagerly loads the associated customer and order so callers can access
        refund.customer.name and refund.order.order_number without triggering
        additional queries.

        Args:
            limit: Maximum number of records to return (default 50, max 200).
        """
        limit = min(limit, 200)
        result = await self._session.execute(
            select(RefundRequest)
            .options(
                selectinload(RefundRequest.customer),
                selectinload(RefundRequest.order),
            )
            .order_by(RefundRequest.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
