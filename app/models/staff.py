"""Staff/Cleaner management models for dispatching cleaners to jobs."""

import enum
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from app.db.base import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StaffStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"
    SUSPENDED = "suspended"


class Staff(Base):
    """A cleaner / staff member who can be dispatched to orders."""

    __tablename__ = "staff"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    status: Mapped[StaffStatus] = mapped_column(
        Enum(StaffStatus, name="staff_status"), default=StaffStatus.ACTIVE
    )
    specializations: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True, default=5.0)
    total_jobs: Mapped[int] = mapped_column(Integer, default=0)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StaffAssignment(Base):
    """Links a staff member to an order for dispatch."""

    __tablename__ = "staff_assignments"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    staff_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("staff.id", ondelete="RESTRICT"), index=True
    )
    assigned_by: Mapped[UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(60), default="cleaner")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order = relationship("Order", backref="staff_assignments")
    staff = relationship("Staff", backref="assignments")
