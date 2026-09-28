import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CustomerNotFoundError
from app.database.connection import get_db
from app.schemas.customer import CustomerResponse
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> CustomerResponse:
    service = CustomerService(db)
    try:
        customer = await service.get_customer(customer_id)
    except CustomerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return CustomerResponse.model_validate(customer)
