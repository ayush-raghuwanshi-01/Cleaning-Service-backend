"""Recurring booking / subscription models for weekly/bi-weekly/monthly cleans."""

import enum
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from app.db.base import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RecurrenceFrequency(str, enum.Enum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


class RecurringOrder(Base):
    """A recurring booking schedule that generates orders automatically."""

    __tablename__ = "recurring_orders"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    customer_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    service_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("services.id", ondelete="RESTRICT")
    )
    service_name: Mapped[str] = mapped_column(String(160), nullable=False)

    frequency: Mapped[RecurrenceFrequency] = mapped_column(
        Enum(RecurrenceFrequency, name="recurrence_frequency"), default=RecurrenceFrequency.WEEKLY
    )
    preferred_day: Mapped[str] = mapped_column(String(20), nullable=False)  # Monday, Tuesday, etc.
    preferred_slot: Mapped[str] = mapped_column(String(60), nullable=False)

    # Address
    street: Mapped[str] = mapped_column(String(255), nullable=False)
    area: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False, default="Bhopal")
    state: Mapped[str] = mapped_column(String(100), nullable=False, default="Madhya Pradesh")
    pincode: Mapped[str] = mapped_column(String(6), nullable=False)
    floor: Mapped[str | None] = mapped_column(String(60), nullable=True)
    landmark: Mapped[str | None] = mapped_column(String(160), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    estimated_hours: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    next_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )