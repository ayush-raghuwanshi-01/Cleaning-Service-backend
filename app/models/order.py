import enum
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# Store enum members by their .value (lowercase) so they match the DB enums
# created in migration 0003 (e.g. 'website', 'requested', 'received', '30min').
def _enum_values(enum_cls):
    return [e.value for e in enum_cls]


class OrderStatus(str, enum.Enum):
    REQUESTED = "requested"
    CONTACTED = "contacted"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OrderSource(str, enum.Enum):
    WEBSITE = "website"
    PHONE = "phone"
    WHATSAPP = "whatsapp"


class PaymentMethod(str, enum.Enum):
    UPI = "UPI"
    CASH = "CASH"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    RECEIVED = "received"


class OrderAddonType(str, enum.Enum):
    MIN30 = "30min"
    MIN60 = "60min"


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    order_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    customer_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    service_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"), index=True)
    service_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source: Mapped[OrderSource] = mapped_column(Enum(OrderSource, name="order_source", values_callable=_enum_values), default=OrderSource.WEBSITE)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus, name="order_status", values_callable=_enum_values), default=OrderStatus.REQUESTED)

    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    customer_email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    street: Mapped[str] = mapped_column(String(255), nullable=False)
    area: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False, default="Bhopal")
    state: Mapped[str] = mapped_column(String(100), nullable=False, default="Madhya Pradesh")
    pincode: Mapped[str] = mapped_column(String(6), nullable=False, index=True)
    floor: Mapped[str | None] = mapped_column(String(60), nullable=True)
    landmark: Mapped[str | None] = mapped_column(String(160), nullable=True)

    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scheduled_slot: Mapped[str] = mapped_column(String(60), nullable=False)

    estimated_hours: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    overtime_hours: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    payments: Mapped[list["Payment"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    addons: Mapped[list["OrderAddon"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    events: Mapped[list["OrderEvent"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod, name="payment_method", values_callable=_enum_values), default=PaymentMethod.UPI)
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus, name="payment_status", values_callable=_enum_values), default=PaymentStatus.RECEIVED)
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    collected_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped[Order] = relationship(back_populates="payments")


class OrderAddon(Base):
    __tablename__ = "order_addons"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    addon_type: Mapped[OrderAddonType] = mapped_column(Enum(OrderAddonType, name="order_addon_type", values_callable=_enum_values), default=OrderAddonType.MIN30)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped[Order] = relationship(back_populates="addons")


class OrderEvent(Base):
    __tablename__ = "order_events"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped[Order] = relationship(back_populates="events")


class WhatsAppConfig(Base):
    __tablename__ = "whatsapp_config"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_group_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    support_number: Mapped[str] = mapped_column(String(20), nullable=False, default="919876543210")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())