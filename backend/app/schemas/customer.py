import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class CustomerResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr
    created_at: datetime

    model_config = {"from_attributes": True}
