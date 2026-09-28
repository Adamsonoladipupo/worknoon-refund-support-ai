import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # final_sale marks whether this item is non-refundable.
    # Stored as a column so the refund policy engine can query it later.
    final_sale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    order: Mapped["Order"] = relationship(  # noqa: F821
        "Order",
        back_populates="items",
        lazy="raise",
    )
