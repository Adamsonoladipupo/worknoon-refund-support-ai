import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )
    order_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # NUMERIC(12,2) gives up to 10 digits before the decimal — sufficient for
    # e-commerce order totals while avoiding floating-point rounding errors.
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    customer: Mapped["Customer"] = relationship(  # noqa: F821
        "Customer",
        back_populates="orders",
        lazy="raise",
    )
    items: Mapped[list["OrderItem"]] = relationship(  # noqa: F821
        "OrderItem",
        back_populates="order",
        lazy="raise",
        cascade="all, delete-orphan",
    )
    refund_requests: Mapped[list["RefundRequest"]] = relationship(  # noqa: F821
        "RefundRequest",
        back_populates="order",
        lazy="raise",
    )
