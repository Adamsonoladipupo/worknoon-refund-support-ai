import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer


class CustomerRepository:
    """All database operations for the Customer model."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, customer_id: uuid.UUID) -> Customer | None:
        result = await self._session.execute(
            select(Customer).where(Customer.id == customer_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Customer | None:
        result = await self._session.execute(
            select(Customer).where(Customer.email == email)
        )
        return result.scalar_one_or_none()
