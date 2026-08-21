from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from app.db.base import GUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ServiceArea(Base):
    __tablename__ = "service_areas"
    __table_args__ = (UniqueConstraint("pincode", name="uq_service_areas_pincode"),)

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    pincode: Mapped[str] = mapped_column(String(6), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Service(Base):
    """A housekeeping service offer.

    Pricing is time-based and set per service. ``base_price`` and
    ``duration_minutes`` describe the headline 2-hour offer (e.g. ₹199 / 2 hrs),
    while the add-on rates let supervisors quote extensions on a call.
    """

    __tablename__ = "services"
    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False, default="express")
    description: Mapped[str | None] = mapped_column(Text)
    blurb: Mapped[str | None] = mapped_column(String(400), nullable=True)
    base_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    price_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    includes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    excludes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Per-service add-on / extension rates (e.g. basic: 30 min = ₹50, 1 hr = ₹80).
    addon_price_30min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    addon_price_60min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Actual time may exceed the estimate by this grace period before add-on
    # rates start applying to the overage.
    overtime_grace_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ServiceAddon(Base):
    __tablename__ = "service_addons"
    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    service_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("services.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Address(Base):
    __tablename__ = "addresses"
    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(60))
    recipient_name: Mapped[str] = mapped_column(String(120))
    recipient_phone: Mapped[str] = mapped_column(String(20))
    line1: Mapped[str] = mapped_column(String(255))
    line2: Mapped[str | None] = mapped_column(String(255))
    landmark: Mapped[str | None] = mapped_column(String(160))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(100))
    pincode: Mapped[str] = mapped_column(String(6), index=True)
    service_area_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("service_areas.id", ondelete="SET NULL"))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())