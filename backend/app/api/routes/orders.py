import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import OrderNotFoundError
from app.database.connection import get_db
from app.schemas.order import OrderResponse
from app.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    service = OrderService(db)
    try:
        order = await service.get_order(order_id)
    except OrderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return OrderResponse.model_validate(order)
