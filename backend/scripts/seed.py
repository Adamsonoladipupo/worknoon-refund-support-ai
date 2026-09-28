"""
Deterministic CRM/order seed data for the Worknoon Refund System.

Run from the backend directory:
    python -m scripts.seed

Design principles
-----------------
* Fixed UUIDs — every customer and order has a hard-coded UUID so test code
  can reference specific records by ID without database lookups.
* Idempotent — existing rows are detected by email (customers) or order_number
  (orders) and skipped, so repeated runs never create duplicates.
* Deterministic dates — all dates are expressed as offsets from a fixed
  REFERENCE_DATE so the relative age of records never changes.
* Decimal monetary values — no Python float is used anywhere.
* No schema changes — the script only INSERTs data; Alembic owns the schema.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.database.connection import AsyncSessionLocal, engine
from app.models.customer import Customer
from app.models.order import Order
from app.models.order_item import OrderItem

# ---------------------------------------------------------------------------
# Fixed reference point so dates are always deterministic.
# All "days ago" offsets are relative to this date.
# ---------------------------------------------------------------------------
REFERENCE_DATE = datetime(2026, 9, 25, 12, 0, 0, tzinfo=timezone.utc)


def days_ago(n: int) -> datetime:
    return REFERENCE_DATE - timedelta(days=n)


# ---------------------------------------------------------------------------
# 15 customers — deterministic UUIDs, synthetic emails, no real PII.
# ---------------------------------------------------------------------------
CUSTOMERS: list[dict] = [
    # fmt: off
    {"id": uuid.UUID("00000000-0000-0000-0000-000000000001"), "name": "Alice Thornton",    "email": "customer01@example.test"},
    {"id": uuid.UUID("00000000-0000-0000-0000-000000000002"), "name": "Bob Mercer",        "email": "customer02@example.test"},
    {"id": uuid.UUID("00000000-0000-0000-0000-000000000003"), "name": "Carol Vance",       "email": "customer03@example.test"},
    {"id": uuid.UUID("00000000-0000-0000-0000-000000000004"), "name": "David Okafor",      "email": "customer04@example.test"},
    {"id": uuid.UUID("00000000-0000-0000-0000-000000000005"), "name": "Eva Lindqvist",     "email": "customer05@example.test"},
    {"id": uuid.UUID("00000000-0000-0000-0000-000000000006"), "name": "Frank Delacroix",   "email": "customer06@example.test"},
    {"id": uuid.UUID("00000000-0000-0000-0000-000000000007"), "name": "Grace Nakamura",    "email": "customer07@example.test"},
    {"id": uuid.UUID("00000000-0000-0000-0000-000000000008"), "name": "Henry Osei",        "email": "customer08@example.test"},
    {"id": uuid.UUID("00000000-0000-0000-0000-000000000009"), "name": "Isabel Ferreira",   "email": "customer09@example.test"},
    {"id": uuid.UUID("00000000-0000-0000-0000-000000000010"), "name": "James Whitfield",   "email": "customer10@example.test"},
    {"id": uuid.UUID("00000000-0000-0000-0000-000000000011"), "name": "Karen Svensson",    "email": "customer11@example.test"},
    {"id": uuid.UUID("00000000-0000-0000-0000-000000000012"), "name": "Liam Oduya",        "email": "customer12@example.test"},
    {"id": uuid.UUID("00000000-0000-0000-0000-000000000013"), "name": "Maria Kowalski",    "email": "customer13@example.test"},
    {"id": uuid.UUID("00000000-0000-0000-0000-000000000014"), "name": "Nathan Brauer",     "email": "customer14@example.test"},
    {"id": uuid.UUID("00000000-0000-0000-0000-000000000015"), "name": "Olivia Tremblay",   "email": "customer15@example.test"},
    # fmt: on
]

# Short aliases for customer UUIDs used in order definitions below.
C = {i + 1: uuid.UUID(f"00000000-0000-0000-0000-{str(i + 1).zfill(12)}") for i in range(15)}

# ---------------------------------------------------------------------------
# Orders — each entry drives one Order + its OrderItems.
#
# Scenario tags (used in comments):
#   NORMAL        — standard eligible refund candidate
#   FINAL_SALE    — contains a final-sale item (non-refundable)
#   HIGH_VALUE    — total > $500 (may require manual approval)
#   OLD           — order_date > 30 days ago (outside refund window)
#   DAMAGED       — recent order flagged for damaged-item refund
#   WRONG_ITEM    — recent order flagged for incorrect-item refund
#   CANCELLED     — order that was cancelled (edge case)
#   PROCESSING    — order still in fulfilment (edge case)
#   ORDINARY      — no special condition
# ---------------------------------------------------------------------------
ORDERS: list[dict] = [

    # ------------------------------------------------------------------
    # Alice (C[1]) — two orders: one normal eligible, one old/expired
    # ------------------------------------------------------------------
    {
        # SCENARIO: NORMAL — standard eligible refund within the window.
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001001"),
        "customer_id":  C[1],
        "order_number": "ORD-1001",
        "order_date":   days_ago(5),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001001"), "product_name": "Wireless Keyboard",     "quantity": 1, "unit_price": Decimal("79.99"),  "final_sale": False},
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001002"), "product_name": "USB-C Hub",             "quantity": 2, "unit_price": Decimal("24.99"),  "final_sale": False},
        ],
    },
    {
        # SCENARIO: OLD — order placed 45 days ago, outside the 30-day window.
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001002"),
        "customer_id":  C[1],
        "order_number": "ORD-1002",
        "order_date":   days_ago(45),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001003"), "product_name": "Laptop Stand",          "quantity": 1, "unit_price": Decimal("49.99"),  "final_sale": False},
        ],
    },

    # ------------------------------------------------------------------
    # Bob (C[2]) — one order with a final-sale item
    # ------------------------------------------------------------------
    {
        # SCENARIO: FINAL_SALE — one item marked final_sale=True; policy
        # engine should deny a refund for that line item.
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001003"),
        "customer_id":  C[2],
        "order_number": "ORD-1003",
        "order_date":   days_ago(8),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001004"), "product_name": "Noise-Cancelling Headphones", "quantity": 1, "unit_price": Decimal("199.99"), "final_sale": False},
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001005"), "product_name": "Clearance Phone Case",        "quantity": 1, "unit_price": Decimal("9.99"),   "final_sale": True},
        ],
    },

    # ------------------------------------------------------------------
    # Carol (C[3]) — one high-value order > $500
    # ------------------------------------------------------------------
    {
        # SCENARIO: HIGH_VALUE — total exceeds $500; may require manual review.
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001004"),
        "customer_id":  C[3],
        "order_number": "ORD-1004",
        "order_date":   days_ago(3),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001006"), "product_name": "4K Monitor",             "quantity": 1, "unit_price": Decimal("449.99"), "final_sale": False},
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001007"), "product_name": "Monitor Arm",            "quantity": 1, "unit_price": Decimal("89.99"),  "final_sale": False},
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001008"), "product_name": "HDMI 2.1 Cable",         "quantity": 2, "unit_price": Decimal("19.99"),  "final_sale": False},
        ],
    },

    # ------------------------------------------------------------------
    # David (C[4]) — damaged-item scenario
    # ------------------------------------------------------------------
    {
        # SCENARIO: DAMAGED — recent order, customer will report item arrived
        # damaged. Should be eligible for full refund.
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001005"),
        "customer_id":  C[4],
        "order_number": "ORD-1005",
        "order_date":   days_ago(2),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001009"), "product_name": "Glass Desk Lamp",        "quantity": 1, "unit_price": Decimal("64.99"),  "final_sale": False},
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001010"), "product_name": "Smart Plug (4-pack)",    "quantity": 1, "unit_price": Decimal("29.99"),  "final_sale": False},
        ],
    },

    # ------------------------------------------------------------------
    # Eva (C[5]) — wrong item received scenario
    # ------------------------------------------------------------------
    {
        # SCENARIO: WRONG_ITEM — customer received the wrong product.
        # Should qualify for a full refund regardless of price.
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001006"),
        "customer_id":  C[5],
        "order_number": "ORD-1006",
        "order_date":   days_ago(4),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001011"), "product_name": "Mechanical Keyboard (Blue Switch)", "quantity": 1, "unit_price": Decimal("129.99"), "final_sale": False},
        ],
    },

    # ------------------------------------------------------------------
    # Frank (C[6]) — cancelled order
    # ------------------------------------------------------------------
    {
        # SCENARIO: CANCELLED — order was cancelled before fulfilment.
        # Refund should be automatic; tests edge-case status handling.
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001007"),
        "customer_id":  C[6],
        "order_number": "ORD-1007",
        "order_date":   days_ago(10),
        "status":       "CANCELLED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001012"), "product_name": "Ergonomic Mouse",        "quantity": 1, "unit_price": Decimal("59.99"),  "final_sale": False},
        ],
    },

    # ------------------------------------------------------------------
    # Grace (C[7]) — order still in processing
    # ------------------------------------------------------------------
    {
        # SCENARIO: PROCESSING — order not yet fulfilled. Refund eligibility
        # may differ from a completed order.
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001008"),
        "customer_id":  C[7],
        "order_number": "ORD-1008",
        "order_date":   days_ago(1),
        "status":       "PROCESSING",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001013"), "product_name": "Webcam 1080p",           "quantity": 1, "unit_price": Decimal("89.99"),  "final_sale": False},
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001014"), "product_name": "Ring Light",             "quantity": 1, "unit_price": Decimal("34.99"),  "final_sale": False},
        ],
    },

    # ------------------------------------------------------------------
    # Henry (C[8]) — two ordinary orders (order history depth)
    # ------------------------------------------------------------------
    {
        # SCENARIO: ORDINARY — standard completed order, no edge case.
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001009"),
        "customer_id":  C[8],
        "order_number": "ORD-1009",
        "order_date":   days_ago(15),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001015"), "product_name": "Desk Organiser",         "quantity": 1, "unit_price": Decimal("22.99"),  "final_sale": False},
        ],
    },
    {
        # SCENARIO: ORDINARY — second order for the same customer.
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001010"),
        "customer_id":  C[8],
        "order_number": "ORD-1010",
        "order_date":   days_ago(6),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001016"), "product_name": "Cable Management Kit",   "quantity": 2, "unit_price": Decimal("14.99"),  "final_sale": False},
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001017"), "product_name": "Sticky Note Set",        "quantity": 3, "unit_price": Decimal("4.99"),   "final_sale": False},
        ],
    },

    # ------------------------------------------------------------------
    # Isabel (C[9]) — three orders (heavy order history)
    # ------------------------------------------------------------------
    {
        # SCENARIO: OLD — outside the 30-day window.
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001011"),
        "customer_id":  C[9],
        "order_number": "ORD-1011",
        "order_date":   days_ago(60),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001018"), "product_name": "Portable SSD 1TB",       "quantity": 1, "unit_price": Decimal("109.99"), "final_sale": False},
        ],
    },
    {
        # SCENARIO: NORMAL — eligible within window.
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001012"),
        "customer_id":  C[9],
        "order_number": "ORD-1012",
        "order_date":   days_ago(20),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001019"), "product_name": "Bluetooth Speaker",      "quantity": 1, "unit_price": Decimal("79.99"),  "final_sale": False},
        ],
    },
    {
        # SCENARIO: FINAL_SALE — all items are final-sale; full denial expected.
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001013"),
        "customer_id":  C[9],
        "order_number": "ORD-1013",
        "order_date":   days_ago(7),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001020"), "product_name": "Clearance Earbuds",      "quantity": 1, "unit_price": Decimal("14.99"),  "final_sale": True},
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001021"), "product_name": "Clearance Phone Stand",  "quantity": 1, "unit_price": Decimal("7.99"),   "final_sale": True},
        ],
    },

    # ------------------------------------------------------------------
    # James (C[10]) — high-value order, older than 30 days
    # ------------------------------------------------------------------
    {
        # SCENARIO: HIGH_VALUE + OLD — expensive order outside the window;
        # should be denied on both grounds.
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001014"),
        "customer_id":  C[10],
        "order_number": "ORD-1014",
        "order_date":   days_ago(40),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001022"), "product_name": "Gaming Laptop",          "quantity": 1, "unit_price": Decimal("1299.99"), "final_sale": False},
        ],
    },

    # ------------------------------------------------------------------
    # Karen (C[11]) — mix: one normal, one with final-sale item
    # ------------------------------------------------------------------
    {
        # SCENARIO: NORMAL — standard eligible order.
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001015"),
        "customer_id":  C[11],
        "order_number": "ORD-1015",
        "order_date":   days_ago(12),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001023"), "product_name": "Adjustable Desk Fan",    "quantity": 1, "unit_price": Decimal("39.99"),  "final_sale": False},
        ],
    },
    {
        # SCENARIO: FINAL_SALE — mixed order: one normal item + one final-sale item.
        # Policy engine should allow refund only for the non-final-sale item.
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001016"),
        "customer_id":  C[11],
        "order_number": "ORD-1016",
        "order_date":   days_ago(9),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001024"), "product_name": "Yoga Mat",               "quantity": 1, "unit_price": Decimal("45.00"),  "final_sale": False},
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001025"), "product_name": "Resistance Bands (Sale)","quantity": 1, "unit_price": Decimal("12.99"),  "final_sale": True},
        ],
    },

    # ------------------------------------------------------------------
    # Liam (C[12]) — DAMAGED scenario (second customer for this scenario)
    # ------------------------------------------------------------------
    {
        # SCENARIO: DAMAGED — fragile item, arrived broken.
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001017"),
        "customer_id":  C[12],
        "order_number": "ORD-1017",
        "order_date":   days_ago(3),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001026"), "product_name": "Ceramic Coffee Mug Set", "quantity": 1, "unit_price": Decimal("34.99"),  "final_sale": False},
        ],
    },

    # ------------------------------------------------------------------
    # Maria (C[13]) — WRONG_ITEM scenario (second customer)
    # ------------------------------------------------------------------
    {
        # SCENARIO: WRONG_ITEM — wrong size/colour delivered.
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001018"),
        "customer_id":  C[13],
        "order_number": "ORD-1018",
        "order_date":   days_ago(6),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001027"), "product_name": "Running Shoes (Size 9)",  "quantity": 1, "unit_price": Decimal("119.99"), "final_sale": False},
        ],
    },

    # ------------------------------------------------------------------
    # Nathan (C[14]) — two ordinary orders
    # ------------------------------------------------------------------
    {
        # SCENARIO: ORDINARY
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001019"),
        "customer_id":  C[14],
        "order_number": "ORD-1019",
        "order_date":   days_ago(25),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001028"), "product_name": "Hardcover Notebook",     "quantity": 2, "unit_price": Decimal("12.99"),  "final_sale": False},
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001029"), "product_name": "Fountain Pen Set",       "quantity": 1, "unit_price": Decimal("29.99"),  "final_sale": False},
        ],
    },
    {
        # SCENARIO: ORDINARY
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001020"),
        "customer_id":  C[14],
        "order_number": "ORD-1020",
        "order_date":   days_ago(11),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001030"), "product_name": "Desk Calendar 2027",     "quantity": 1, "unit_price": Decimal("9.99"),   "final_sale": False},
        ],
    },

    # ------------------------------------------------------------------
    # Olivia (C[15]) — HIGH_VALUE recent order
    # ------------------------------------------------------------------
    {
        # SCENARIO: HIGH_VALUE — recent expensive order, within window.
        # Should trigger manual review path in the policy engine.
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001021"),
        "customer_id":  C[15],
        "order_number": "ORD-1021",
        "order_date":   days_ago(2),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001031"), "product_name": "Standing Desk (Electric)", "quantity": 1, "unit_price": Decimal("649.99"), "final_sale": False},
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001032"), "product_name": "Anti-Fatigue Mat",          "quantity": 1, "unit_price": Decimal("59.99"),  "final_sale": False},
        ],
    },

    # ------------------------------------------------------------------
    # Extra ordinary orders spread across remaining customers
    # to bring the total to ~25 orders and deepen order history.
    # ------------------------------------------------------------------
    {
        # SCENARIO: ORDINARY — C[2] second order (Bob has history)
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001022"),
        "customer_id":  C[2],
        "order_number": "ORD-1022",
        "order_date":   days_ago(30),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001033"), "product_name": "Screen Cleaning Kit",    "quantity": 1, "unit_price": Decimal("11.99"),  "final_sale": False},
        ],
    },
    {
        # SCENARIO: ORDINARY — C[3] second order (Carol has history)
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001023"),
        "customer_id":  C[3],
        "order_number": "ORD-1023",
        "order_date":   days_ago(50),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001034"), "product_name": "Wrist Rest Pad",         "quantity": 1, "unit_price": Decimal("19.99"),  "final_sale": False},
        ],
    },
    {
        # SCENARIO: ORDINARY — C[5] second order
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001024"),
        "customer_id":  C[5],
        "order_number": "ORD-1024",
        "order_date":   days_ago(18),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001035"), "product_name": "Laptop Bag 15\"",        "quantity": 1, "unit_price": Decimal("44.99"),  "final_sale": False},
        ],
    },
    {
        # SCENARIO: ORDINARY — C[6] second order (Frank has history beyond cancelled)
        "id":           uuid.UUID("10000000-0000-0000-0000-000000001025"),
        "customer_id":  C[6],
        "order_number": "ORD-1025",
        "order_date":   days_ago(22),
        "status":       "COMPLETED",
        "items": [
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001036"), "product_name": "Mousepad XL",            "quantity": 1, "unit_price": Decimal("24.99"),  "final_sale": False},
            {"id": uuid.UUID("20000000-0000-0000-0000-000000001037"), "product_name": "USB 3.0 Hub",            "quantity": 1, "unit_price": Decimal("19.99"),  "final_sale": False},
        ],
    },
]


def compute_total(items: list[dict]) -> Decimal:
    """Sum quantity * unit_price for all items in an order definition."""
    return sum(
        item["quantity"] * item["unit_price"]
        for item in items
    )


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        # ------------------------------------------------------------------
        # 1. Seed customers — skip any that already exist by email.
        # ------------------------------------------------------------------
        customers_inserted = 0
        existing_emails_result = await session.execute(select(Customer.email))
        existing_emails: set[str] = set(existing_emails_result.scalars().all())

        for c in CUSTOMERS:
            if c["email"] in existing_emails:
                continue
            session.add(Customer(
                id=c["id"],
                name=c["name"],
                email=c["email"],
            ))
            customers_inserted += 1

        await session.flush()  # make customer PKs visible for FK references below

        # ------------------------------------------------------------------
        # 2. Seed orders — skip any that already exist by order_number.
        # ------------------------------------------------------------------
        orders_inserted = 0
        items_inserted = 0

        existing_orders_result = await session.execute(select(Order.order_number))
        existing_order_numbers: set[str] = set(existing_orders_result.scalars().all())

        for o in ORDERS:
            if o["order_number"] in existing_order_numbers:
                continue

            total = compute_total(o["items"])
            order = Order(
                id=o["id"],
                customer_id=o["customer_id"],
                order_number=o["order_number"],
                order_date=o["order_date"],
                total_amount=total,
                status=o["status"],
            )
            session.add(order)

            for item_data in o["items"]:
                session.add(OrderItem(
                    id=item_data["id"],
                    order_id=o["id"],
                    product_name=item_data["product_name"],
                    quantity=item_data["quantity"],
                    unit_price=item_data["unit_price"],
                    final_sale=item_data["final_sale"],
                ))
                items_inserted += 1

            orders_inserted += 1

        await session.commit()

    # ------------------------------------------------------------------
    # 3. Print summary.
    # ------------------------------------------------------------------
    total_customers = len(CUSTOMERS)
    total_orders = len(ORDERS)
    total_items = sum(len(o["items"]) for o in ORDERS)

    print("Seed completed successfully.")
    print(f"Customers : {total_customers} defined  |  {customers_inserted} inserted  |  {total_customers - customers_inserted} skipped")
    print(f"Orders    : {total_orders} defined  |  {orders_inserted} inserted  |  {total_orders - orders_inserted} skipped")
    print(f"Order items: {total_items} defined  |  {items_inserted} inserted")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
