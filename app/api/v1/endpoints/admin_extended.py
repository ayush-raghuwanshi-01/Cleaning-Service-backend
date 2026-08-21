from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, func as sa_func
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, get_current_user, require_operations
from app.models.business import Service
from app.models.order import Order, OrderStatus, Payment
from app.models.staff import StaffAssignment as ORMStaffAssignment
from app.models.staff import Staff, StaffStatus
from app.models.recurring import RecurringOrder
from app.models.user import AuditLog, User
from app.schemas.order import (
    AuditLogResponse,
    StaffResponse,
    StaffCreateRequest,
    StaffUpdateRequest,
    StaffAssignmentResponse,
    StaffAssignmentCreateRequest,
    RecurringOrderResponse,
    RecurringOrderCreateRequest,
    RecurringOrderUpdateRequest,
)
from app.services.orders import add_event, get_order_or_404, transition
from app.services.notifications import notify_cleaner_dispatched, notify_order_completed, notify_order_confirmed
from app.services.reports import generate_csv_report, generate_revenue_summary

router = APIRouter(prefix="/admin", tags=["admin-extended"])


# --------------------------------------------------------------------------- #
# Audit Log Endpoint
# --------------------------------------------------------------------------- #
@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def list_audit_logs(
    session: DbSession,
    actor: Annotated[User, Depends(require_operations)],
    limit: int = Query(200, ge=1, le=1000),
) -> list[AuditLog]:
    return list(
        (await session.scalars(
            select(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )).all()
    )


# --------------------------------------------------------------------------- #
# Staff Management
# --------------------------------------------------------------------------- #
@router.get("/staff", response_model=list[StaffResponse])
async def list_staff(
    session: DbSession,
    actor: Annotated[User, Depends(require_operations)],
) -> list[Staff]:
    return list(
        (await session.scalars(
            select(Staff).order_by(Staff.full_name)
        )).all()
    )


@router.post("/staff", response_model=StaffResponse, status_code=status.HTTP_201_CREATED)
async def create_staff(
    payload: StaffCreateRequest,
    session: DbSession,
    actor: Annotated[User, Depends(require_operations)],
) -> Staff:
    staff = Staff(**payload.model_dump())
    session.add(staff)
    session.add(
        AuditLog(actor_id=actor.id, action="staff_created", entity_type="staff", entity_id=str(staff.id))
    )
    await session.commit()
    await session.refresh(staff)
    return staff


@router.patch("/staff/{staff_id}", response_model=StaffResponse)
async def update_staff(
    staff_id: UUID,
    payload: StaffUpdateRequest,
    session: DbSession,
    actor: Annotated[User, Depends(require_operations)],
) -> Staff:
    staff = await session.get(Staff, staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")
    for name, value in payload.model_dump(exclude_unset=True).items():
        setattr(staff, name, value)
    session.add(
        AuditLog(actor_id=actor.id, action="staff_updated", entity_type="staff", entity_id=str(staff.id))
    )
    await session.commit()
    await session.refresh(staff)
    return staff


@router.post(
    "/orders/{order_id}/assign",
    response_model=StaffAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_staff_to_order(
    order_id: UUID,
    payload: StaffAssignmentCreateRequest,
    session: DbSession,
    actor: Annotated[User, Depends(require_operations)],
) -> ORMStaffAssignment:
    order = await get_order_or_404(session, order_id)
    staff = await session.get(Staff, payload.staff_id)
    if not staff or staff.status != StaffStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff not found or not active",
        )
    assignment = ORMStaffAssignment(
        order_id=order.id,
        staff_id=payload.staff_id,
        assigned_by=actor.id,
        role=payload.role,
        notes=payload.notes,
    )
    session.add(assignment)
    await add_event(
        session,
        order.id,
        "staff_assigned",
        f"Staff {staff.full_name} assigned as {payload.role}.",
        actor,
    )
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="staff_assigned",
            entity_type="staff_assignment",
            entity_id=str(assignment.id),
        )
    )

    # Notify customer about dispatch
    notify_cleaner_dispatched(
        order.customer_phone,
        order.customer_name,
        staff.full_name,
        order.order_code,
        order.scheduled_slot,
    )

    await session.commit()
    await session.refresh(assignment)
    return assignment


@router.get("/orders/{order_id}/assignments", response_model=list[StaffAssignmentResponse])
async def list_order_assignments(
    order_id: UUID,
    session: DbSession,
    actor: Annotated[User, Depends(require_operations)],
) -> list[ORMStaffAssignment]:
    order = await get_order_or_404(session, order_id)
    return list(order.staff_assignments)


@router.post(
    "/orders/{order_id}/assignments/{assignment_id}/complete",
    response_model=StaffAssignmentResponse,
)
async def complete_staff_assignment(
    order_id: UUID,
    assignment_id: UUID,
    session: DbSession,
    actor: Annotated[User, Depends(require_operations)],
) -> ORMStaffAssignment:
    assignment = await session.get(ORMStaffAssignment, assignment_id)
    if not assignment or assignment.order_id != order_id:
        raise HTTPException(status_code=404, detail="Assignment not found")
    assignment.completed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(assignment)
    return assignment


# --------------------------------------------------------------------------- #
# Recurring Orders
# --------------------------------------------------------------------------- #
@router.get("/recurring-orders", response_model=list[RecurringOrderResponse])
async def list_recurring_orders(
    session: DbSession,
    actor: Annotated[User, Depends(require_operations)],
) -> list[RecurringOrder]:
    return list(
        (await session.scalars(
            select(RecurringOrder)
            .where(RecurringOrder.is_active == True)
            .order_by(RecurringOrder.created_at.desc())
        )).all()
    )


@router.post(
    "/recurring-orders",
    response_model=RecurringOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_recurring_order(
    payload: RecurringOrderCreateRequest,
    session: DbSession,
    actor: Annotated[User, Depends(require_operations)],
) -> RecurringOrder:
    service = await session.get(Service, payload.service_id)
    if not service or not service.is_active:
        raise HTTPException(status_code=404, detail="Service not found")

    data = payload.model_dump()
    data["service_name"] = service.name
    recurring = RecurringOrder(**data)
    session.add(recurring)
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="recurring_order_created",
            entity_type="recurring_order",
            entity_id=str(recurring.id),
        )
    )
    await session.commit()
    await session.refresh(recurring)
    return recurring


@router.patch(
    "/recurring-orders/{recurring_id}",
    response_model=RecurringOrderResponse,
)
async def update_recurring_order(
    recurring_id: UUID,
    payload: RecurringOrderUpdateRequest,
    session: DbSession,
    actor: Annotated[User, Depends(require_operations)],
) -> RecurringOrder:
    recurring = await session.get(RecurringOrder, recurring_id)
    if not recurring:
        raise HTTPException(status_code=404, detail="Recurring order not found")
    for name, value in payload.model_dump(exclude_unset=True).items():
        setattr(recurring, name, value)
    await session.commit()
    await session.refresh(recurring)
    return recurring


# --------------------------------------------------------------------------- #
# Reports & Exports
# --------------------------------------------------------------------------- #
@router.get("/reports/csv")
async def export_csv(
    session: DbSession,
    actor: Annotated[User, Depends(require_operations)],
    start_date: date = Query(...),
    end_date: date = Query(...),
) -> Response:
    csv_content = await generate_csv_report(session, start_date, end_date)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=orders_report_{start_date}_{end_date}.csv"
        },
    )


@router.get("/reports/revenue-summary")
async def revenue_summary(
    session: DbSession,
    actor: Annotated[User, Depends(require_operations)],
    start_date: date = Query(...),
    end_date: date = Query(...),
) -> dict:
    return await generate_revenue_summary(session, start_date, end_date)


# --------------------------------------------------------------------------- #
# Dashboard alerts / pipeline stats
# --------------------------------------------------------------------------- #
@router.get("/dashboard-alerts")
async def dashboard_alerts(
    session: DbSession,
    actor: Annotated[User, Depends(require_operations)],
) -> dict:
    today = date.today()

    # Unassigned jobs today (requested/confirmed but no staff assigned)
    unassigned = (
        await session.scalar(
            select(sa_func.count())
            .select_from(Order)
            .where(
                Order.scheduled_date == today,
                Order.status.in_([
                    OrderStatus.REQUESTED,
                    OrderStatus.CONTACTED,
                    OrderStatus.CONFIRMED,
                    OrderStatus.IN_PROGRESS,
                ]),
                ~Order.id.in_(
                    select(ORMStaffAssignment.order_id).where(
                        ORMStaffAssignment.completed_at.is_(None)
                    )
                ),
            )
        )
    ) or 0

    # Overdue payments (completed but unpaid)
    overdue = (
        await session.scalar(
            select(sa_func.count())
            .select_from(Order)
            .where(
                Order.status == OrderStatus.COMPLETED,
                ~Order.id.in_(
                    select(Payment.order_id).where(
                        Payment.status == "received"
                    )
                ),
            )
        )
    ) or 0

    # Pipeline counts
    pipeline = {}
    for s in OrderStatus:
        count = (
            await session.scalar(
                select(sa_func.count()).select_from(Order).where(Order.status == s)
            )
        ) or 0
        pipeline[s.value] = count

    return {
        "unassigned_jobs": unassigned,
        "overdue_payments": overdue,
        "today": today.isoformat(),
        "pipeline": pipeline,
    }