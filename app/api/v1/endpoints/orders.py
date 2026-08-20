from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, get_current_user, require_operations
from app.models.business import Service
from app.models.order import (
    Order,
    OrderAddon,
    OrderEvent,
    OrderSource,
    OrderStatus,
    Payment,
    PaymentMethod,
    WhatsAppConfig,
)
from app.models.user import AuditLog, User
from app.schemas.order import (
    DayStatsResponse,
    OrderAddonCreateRequest,
    OrderAdminCreateRequest,
    OrderCreateRequest,
    OrderDetailResponse,
    OrderStatusRequest,
    OrderSummaryResponse,
    OrderUpdateRequest,
    PaymentCreateRequest,
    PaymentResponse,
    WhatsAppConfigInput,
    WhatsAppConfigResponse,
)
from app.services.orders import (
    add_event,
    get_order_or_404,
    new_order_code,
    payment_status,
    payment_summary,
    transition,
)

public_router = APIRouter(tags=["orders"])
customer_router = APIRouter(prefix="/orders", tags=["orders"])
admin_router = APIRouter(prefix="/admin", tags=["orders"])


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _decorate_detail(order: Order) -> Order:
    order.payment_status = payment_status(order)
    order.payment_summary = payment_summary(order)
    return order


async def _load_order(session: AsyncSession, order_id: UUID) -> Order:
    """Fetch an order with payments/addons/events eagerly loaded (async-safe)."""
    order = await session.scalar(
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.payments),
            selectinload(Order.addons),
            selectinload(Order.events),
        )
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _decorate_detail(order)


# --------------------------------------------------------------------------- #
# Public — light order tracking by order code (no sensitive data)
# --------------------------------------------------------------------------- #
@public_router.get("/orders/track/{order_code}")
async def track_order(order_code: str, session: DbSession) -> dict:
    order = await session.scalar(select(Order).where(Order.order_code == order_code.upper()))
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    events = list(
        (
            await session.scalars(
                select(OrderEvent).where(OrderEvent.order_id == order.id).order_by(OrderEvent.created_at)
            )
        ).all()
    )
    return {
        "order_code": order.order_code,
        "service_name": order.service_name,
        "status": order.status.value,
        "scheduled_date": order.scheduled_date.isoformat(),
        "scheduled_slot": order.scheduled_slot,
        "events": [
            {"event_type": e.event_type, "message": e.message, "created_at": e.created_at.isoformat()}
            for e in events
        ],
    }


# --------------------------------------------------------------------------- #
# Customer — create & view own orders (login required to order)
# --------------------------------------------------------------------------- #
@customer_router.post("", response_model=OrderDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreateRequest,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> Order:
    service = await session.get(Service, payload.service_id)
    if not service or not service.is_active:
        raise HTTPException(status_code=404, detail="Service not found")

    data = payload.model_dump()
    data["service_id"] = service.id
    data["service_name"] = service.name

    order = Order(
        order_code=new_order_code(),
        customer_id=user.id,
        source=OrderSource.WEBSITE,
        status=OrderStatus.REQUESTED,
        customer_name=user.full_name,
        customer_phone=user.phone,
        customer_email=user.email,
        **data,
    )
    session.add(order)
    await session.flush()
    await add_event(
        session,
        order.id,
        "order_created",
        f"Request placed by {user.full_name} for {service.name} on {order.scheduled_date} ({order.scheduled_slot}).",
        user,
    )
    session.add(AuditLog(actor_id=user.id, action="order_created", entity_type="order", entity_id=str(order.id)))
    await session.commit()
    return await _load_order(session, order.id)

@customer_router.get("", response_model=list[OrderSummaryResponse])
async def my_orders(session: DbSession, user: Annotated[User, Depends(get_current_user)]) -> list[Order]:
    return list(
        (
            await session.scalars(
                select(Order).where(Order.customer_id == user.id).order_by(Order.created_at.desc())
            )
        ).all()
    )


@customer_router.get("/{order_id}", response_model=OrderDetailResponse)
async def get_my_order(
    order_id: UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> Order:
    order = await session.scalar(
        select(Order)
        .where(Order.id == order_id, Order.customer_id == user.id)
        .options(
            selectinload(Order.payments),
            selectinload(Order.addons),
            selectinload(Order.events),
        )
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _decorate_detail(order)


@customer_router.post("/{order_id}/cancel", response_model=OrderDetailResponse)
async def cancel_my_order(
    order_id: UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> Order:
    order = await session.scalar(
        select(Order)
        .where(Order.id == order_id, Order.customer_id == user.id)
        .options(
            selectinload(Order.payments),
            selectinload(Order.addons),
            selectinload(Order.events),
        )
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    await transition(session, order, OrderStatus.CANCELLED, user, "Cancelled by customer")
    session.add(AuditLog(actor_id=user.id, action="order_cancelled", entity_type="order", entity_id=str(order.id)))
    await session.commit()
    return await _load_order(session, order.id)


# --------------------------------------------------------------------------- #
# Admin / Ops — dashboard
# --------------------------------------------------------------------------- #
@admin_router.get("/orders", response_model=list[OrderSummaryResponse])
async def list_orders(
    session: DbSession,
    actor: Annotated[User, Depends(require_operations)],
    status_filter: Annotated[OrderStatus | None, Query(alias="status")] = None,
    source: Annotated[OrderSource | None, Query()] = None,
    scheduled_date: Annotated[date | None, Query()] = None,
    area: Annotated[str | None, Query()] = None,
) -> list[Order]:
    stmt = select(Order)
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    if source:
        stmt = stmt.where(Order.source == source)
    if scheduled_date:
        stmt = stmt.where(Order.scheduled_date == scheduled_date)
    if area:
        stmt = stmt.where(Order.area == area)
    stmt = stmt.order_by(Order.scheduled_date.desc(), Order.created_at.desc())
    return list((await session.scalars(stmt)).all())


@admin_router.post("/orders", response_model=OrderDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_admin_order(
    payload: OrderAdminCreateRequest,
    session: DbSession,
    actor: Annotated[User, Depends(require_operations)],
) -> Order:
    service = await session.get(Service, payload.service_id)
    if not service or not service.is_active:
        raise HTTPException(status_code=404, detail="Service not found")

    data = payload.model_dump()
    data["service_id"] = service.id
    data["service_name"] = service.name

    order = Order(
        order_code=new_order_code(),
        status=OrderStatus.REQUESTED,
        **data,
    )
    session.add(order)
    await session.flush()
    await add_event(
        session,
        order.id,
        "order_created",
        f"Order logged from {payload.source.value} for {service.name} — {payload.customer_name} ({payload.customer_phone}).",
        actor,
    )
    session.add(AuditLog(actor_id=actor.id, action="order_created", entity_type="order", entity_id=str(order.id)))
    await session.commit()
    return await _load_order(session, order.id)

@admin_router.get("/orders/{order_id}", response_model=OrderDetailResponse)
async def get_admin_order(
    order_id: UUID, session: DbSession, actor: Annotated[User, Depends(require_operations)]
) -> Order:
    return await _load_order(session, order_id)


@admin_router.patch("/orders/{order_id}", response_model=OrderDetailResponse)
async def update_order(
    order_id: UUID,
    payload: OrderUpdateRequest,
    session: DbSession,
    actor: Annotated[User, Depends(require_operations)],
) -> Order:
    order = await get_order_or_404(session, order_id)
    changes: list[str] = []
    data = payload.model_dump(exclude_unset=True)
    if "service_id" in data:
        service = await session.get(Service, data["service_id"])
        if not service or not service.is_active:
            raise HTTPException(status_code=404, detail="Service not found")
        order.service_id = service.id
        order.service_name = service.name
        changes.append(f"service → {service.name}")
        data.pop("service_id")
    for name, value in data.items():
        setattr(order, name, value)
        changes.append(name.replace("_", " "))
    if changes:
        await add_event(
            session, order.id, "order_updated", f"Updated: {', '.join(changes)}.", actor
        )
    session.add(AuditLog(actor_id=actor.id, action="order_updated", entity_type="order", entity_id=str(order.id)))
    await session.commit()
    return await _load_order(session, order.id)


@admin_router.post("/orders/{order_id}/status", response_model=OrderDetailResponse)
async def set_order_status(
    order_id: UUID,
    payload: OrderStatusRequest,
    session: DbSession,
    actor: Annotated[User, Depends(require_operations)],
) -> Order:
    order = await get_order_or_404(session, order_id)
    await transition(session, order, payload.status, actor)
    session.add(AuditLog(actor_id=actor.id, action="order_status_changed", entity_type="order", entity_id=str(order.id)))
    await session.commit()
    return await _load_order(session, order.id)


@admin_router.post("/orders/{order_id}/addons", response_model=OrderDetailResponse, status_code=status.HTTP_201_CREATED)
async def add_order_addon(
    order_id: UUID,
    payload: OrderAddonCreateRequest,
    session: DbSession,
    actor: Annotated[User, Depends(require_operations)],
) -> Order:
    order = await get_order_or_404(session, order_id)
    addon = OrderAddon(order_id=order.id, **payload.model_dump())
    session.add(addon)
    await add_event(
        session,
        order.id,
        "addon_added",
        f"Add-on {payload.addon_type.value} x{payload.quantity} @ ₹{payload.price}.",
        actor,
    )
    await session.commit()
    return await _load_order(session, order.id)


@admin_router.post("/orders/{order_id}/payments", response_model=OrderDetailResponse, status_code=status.HTTP_201_CREATED)
async def record_payment(
    order_id: UUID,
    payload: PaymentCreateRequest,
    session: DbSession,
    actor: Annotated[User, Depends(require_operations)],
) -> Order:
    order = await get_order_or_404(session, order_id)
    payment = Payment(
        order_id=order.id,
        amount=payload.amount,
        method=payload.method,
        status=payload.status,
        reference=payload.reference,
        notes=payload.notes,
        collected_by=actor.id,
        collected_at=datetime.now(UTC) if payload.status == "received" else None,
    )
    session.add(payment)
    method_label = "UPI" if payload.method == PaymentMethod.UPI else "Cash"
    ref = f" (Ref {payload.reference})" if payload.reference else ""
    await add_event(
        session,
        order.id,
        "payment_received",
        f"Payment ₹{payload.amount} {method_label}{ref} recorded.",
        actor,
    )
    session.add(AuditLog(actor_id=actor.id, action="payment_recorded", entity_type="payment", entity_id=str(payment.id)))
    await session.commit()
    return await _load_order(session, order.id)


@admin_router.get("/orders/{order_id}/payments", response_model=list[PaymentResponse])
async def list_order_payments(
    order_id: UUID, session: DbSession, actor: Annotated[User, Depends(require_operations)]
) -> list[Payment]:
    order = await get_order_or_404(session, order_id)
    return list(order.payments)


@admin_router.get("/stats", response_model=DayStatsResponse)
async def day_stats(session: DbSession, actor: Annotated[User, Depends(require_operations)], day: Annotated[date | None, Query()] = None) -> DayStatsResponse:
    target = day or date.today()
    orders = list(
        (
            await session.scalars(
                select(Order)
                .where(Order.scheduled_date == target)
                .options(selectinload(Order.payments))
            )
        ).all()
    )
    revenue = Decimal("0")
    revenue_upi = Decimal("0")
    revenue_cash = Decimal("0")
    by_source: dict[str, int] = {}
    completed = 0
    for order in orders:
        by_source[order.source.value] = by_source.get(order.source.value, 0) + 1
        if order.status == OrderStatus.COMPLETED:
            completed += 1
        for payment in order.payments:
            if payment.status == "received":
                revenue += payment.amount
                if payment.method == PaymentMethod.UPI:
                    revenue_upi += payment.amount
                else:
                    revenue_cash += payment.amount
    return DayStatsResponse(
        date=target,
        orders=len(orders),
        completed_orders=completed,
        revenue=revenue,
        revenue_upi=revenue_upi,
        revenue_cash=revenue_cash,
        by_source=by_source,
    )

# --------------------------------------------------------------------------- #
# WhatsApp config
# --------------------------------------------------------------------------- #
async def _get_whatsapp_config(session: AsyncSession) -> WhatsAppConfig:
    cfg = await session.get(WhatsAppConfig, 1)
    if not cfg:
        cfg = WhatsAppConfig(id=1, support_number="919876543210")
        session.add(cfg)
        await session.commit()
        await session.refresh(cfg)
    return cfg


@admin_router.get("/whatsapp-config", response_model=WhatsAppConfigResponse)
async def get_whatsapp_config(
    session: DbSession, actor: Annotated[User, Depends(require_operations)]
) -> WhatsAppConfig:
    return await _get_whatsapp_config(session)


@admin_router.patch("/whatsapp-config", response_model=WhatsAppConfigResponse)
async def update_whatsapp_config(
    payload: WhatsAppConfigInput,
    session: DbSession,
    actor: Annotated[User, Depends(require_operations)],
) -> WhatsAppConfig:
    cfg = await _get_whatsapp_config(session)
    cfg.staff_group_link = payload.staff_group_link
    cfg.support_number = payload.support_number
    await session.commit()
    await session.refresh(cfg)
    return cfg