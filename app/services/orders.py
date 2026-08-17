"""Business logic for orders, payments, add-ons and the audit timeline.

Kept separate from the HTTP endpoints so the status machine and payment
derivation are central and testable.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderEvent, OrderStatus
from app.models.user import User

# A terminal status can never transition anywhere.
TERMINAL: frozenset[str] = frozenset({OrderStatus.COMPLETED.value, OrderStatus.CANCELLED.value})

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    OrderStatus.REQUESTED.value: {OrderStatus.CONTACTED.value, OrderStatus.CANCELLED.value},
    OrderStatus.CONTACTED.value: {OrderStatus.CONFIRMED.value, OrderStatus.CANCELLED.value},
    OrderStatus.CONFIRMED.value: {OrderStatus.IN_PROGRESS.value, OrderStatus.CANCELLED.value},
    OrderStatus.IN_PROGRESS.value: {OrderStatus.COMPLETED.value, OrderStatus.CANCELLED.value},
    OrderStatus.COMPLETED.value: set(),
    OrderStatus.CANCELLED.value: set(),
}


def new_order_code() -> str:
    return "SH-" + uuid4().hex[:6].upper()


def can_transition(current: OrderStatus, next_status: OrderStatus) -> bool:
    if current.value in TERMINAL:
        return False
    return next_status.value in ALLOWED_TRANSITIONS.get(current.value, set())


def _transition_error(current: OrderStatus, next_status: OrderStatus) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"Cannot move order from '{current.value}' to '{next_status.value}'",
    )


async def add_event(
    session: AsyncSession,
    order_id: UUID,
    event_type: str,
    message: str,
    actor: User | None = None,
    metadata_json: str | None = None,
) -> None:
    session.add(
        OrderEvent(
            order_id=order_id,
            event_type=event_type,
            actor_id=actor.id if actor else None,
            message=message,
            metadata_json=metadata_json,
        )
    )


async def transition(
    session: AsyncSession,
    order: Order,
    next_status: OrderStatus,
    actor: User | None = None,
    message: str | None = None,
) -> None:
    """Validate and apply a status transition, stamping timestamps + an event."""

    if order.status == next_status:
        return
    if not can_transition(order.status, next_status):
        raise _transition_error(order.status, next_status)

    order.status = next_status
    now = datetime.now(UTC)
    if next_status == OrderStatus.IN_PROGRESS and order.started_at is None:
        order.started_at = now
    if next_status == OrderStatus.COMPLETED:
        order.completed_at = now
    if next_status == OrderStatus.CANCELLED:
        order.cancelled_at = now

    if message is None:
        message = f"Order status changed to '{next_status.value}'"
    await add_event(session, order.id, "status_changed", message, actor)


def received_amount(order: Order) -> Decimal:
    return sum((p.amount for p in order.payments if p.status == "received"), Decimal("0"))


def payment_status(order: Order) -> str:
    """Derive the order's overall paid state from its payment rows."""
    received = received_amount(order)
    if received <= 0:
        return "unpaid"
    if order.amount is not None and received >= order.amount:
        return "paid"
    return "partial"


def payment_summary(order: Order) -> str:
    received = received_amount(order)
    amount = order.amount
    if received <= 0:
        return "Unpaid"
    if amount is not None and received >= amount:
        return f"Paid ₹{amount}"
    if amount is not None:
        return f"Paid ₹{received} of ₹{amount}"
    return f"Paid ₹{received}"


async def get_order_or_404(session: AsyncSession, order_id: UUID) -> Order:
    order = await session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order