import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        # Let the database generate the timestamp so it's consistent across
        # application instances and not subject to clock drift.
        server_default=func.now(),
        nullable=False,
    )

    # lazy="raise" forces explicit eager-loading, preventing accidental N+1
    # queries in async contexts.
    orders: Mapped[list["Order"]] = relationship(  # noqa: F821
        "Order",
        back_populates="customer",
        lazy="raise",
    )
    refund_requests: Mapped[list["RefundRequest"]] = relationship(  # noqa: F821
        "RefundRequest",
        back_populates="customer",
        lazy="raise",
    )
