import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order


class OrderRepository:
    """All database operations for the Order model."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, order_id: uuid.UUID) -> Order | None:
        # selectinload avoids the N+1 problem: items are fetched in a single
        # additional query rather than one query per item row.
        result = await self._session.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id)
        )
        return result.scalar_one_or_none()

    async def get_by_order_number(self, order_number: str) -> Order | None:
        result = await self._session.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.order_number == order_number)
        )
        return result.scalar_one_or_none()

    async def get_by_customer_id(self, customer_id: uuid.UUID) -> list[Order]:
        result = await self._session.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.customer_id == customer_id)
            .order_by(Order.order_date.desc())
        )
        return list(result.scalars().all())
