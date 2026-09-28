import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CustomerNotFoundError
from app.models.customer import Customer
from app.repositories.customer_repository import CustomerRepository


class CustomerService:
    """Business logic for customer operations.

    The service layer sits between routes and repositories. It is the right
    place to add validation, authorization checks, or cross-cutting concerns
    without cluttering either the HTTP layer or the query layer.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._repo = CustomerRepository(session)

    async def get_customer(self, customer_id: uuid.UUID) -> Customer:
        customer = await self._repo.get_by_id(customer_id)
        if customer is None:
            raise CustomerNotFoundError(customer_id)
        return customer
