import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class OrderItemResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    product_name: str
    quantity: int
    unit_price: Decimal
    final_sale: bool

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    order_number: str
    order_date: datetime
    total_amount: Decimal
    status: str
    created_at: datetime
    items: list[OrderItemResponse]

    model_config = {"from_attributes": True}
