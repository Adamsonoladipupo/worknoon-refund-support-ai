import uuid
from decimal import Decimal


class CustomerNotFoundError(Exception):
    """Raised when a customer cannot be found by the given identifier."""

    def __init__(self, customer_id: uuid.UUID) -> None:
        self.customer_id = customer_id
        super().__init__(f"Customer {customer_id} not found.")


class OrderNotFoundError(Exception):
    """Raised when an order cannot be found by the given identifier."""

    def __init__(self, identifier: str | uuid.UUID) -> None:
        self.identifier = identifier
        super().__init__(f"Order '{identifier}' not found.")


class InvalidRefundAmountError(Exception):
    """Raised when the requested refund amount fails business validation.

    Covers: zero amount, negative amount, and amount exceeding the order total.
    """

    def __init__(self, message: str, amount: Decimal | None = None) -> None:
        self.amount = amount
        super().__init__(message)
