import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import OrderNotFoundError
from app.models.order import Order
from app.repositories.order_repository import OrderRepository


class OrderService:
    """Business logic for order operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = OrderRepository(session)

    async def get_order(self, order_id: uuid.UUID) -> Order:
        order = await self._repo.get_by_id(order_id)
        if order is None:
            raise OrderNotFoundError(order_id)
        return order

    async def get_order_by_number(self, order_number: str) -> Order:
        order = await self._repo.get_by_order_number(order_number)
        if order is None:
            raise OrderNotFoundError(order_number)
        return order
