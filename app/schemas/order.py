from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.order import (
    OrderAddonType,
    OrderSource,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
)


# --------------------------------------------------------------------------- #
# Customer-facing
# --------------------------------------------------------------------------- #
class SiteInfo(BaseModel):
    street: str = Field(min_length=3, max_length=255)
    area: str = Field(min_length=2, max_length=120)
    city: str = Field(default="Bhopal", min_length=2, max_length=100)
    state: str = Field(default="Madhya Pradesh", min_length=2, max_length=100)
    pincode: str = Field(pattern=r"^\d{6}$")
    floor: str | None = Field(default=None, max_length=60)
    landmark: str | None = Field(default=None, max_length=160)


class OrderCreateRequest(SiteInfo):
    service_id: UUID
    scheduled_date: date
    scheduled_slot: str = Field(min_length=2, max_length=60)
    description: str | None = Field(default=None, max_length=4000)


# --------------------------------------------------------------------------- #
# Supervisor / admin intake & editing
# --------------------------------------------------------------------------- #
class OrderAdminCreateRequest(BaseModel):
    source: OrderSource = OrderSource.WEBSITE
    customer_name: str = Field(min_length=2, max_length=120)
    customer_phone: str = Field(pattern=r"^\+?[1-9]\d{7,14}$")
    customer_email: EmailStr | None = None
    service_id: UUID
    scheduled_date: date
    scheduled_slot: str = Field(min_length=2, max_length=60)
    street: str = Field(min_length=3, max_length=255)
    area: str = Field(min_length=2, max_length=120)
    city: str = Field(default="Bhopal", min_length=2, max_length=100)
    state: str = Field(default="Madhya Pradesh", min_length=2, max_length=100)
    pincode: str = Field(pattern=r"^\d{6}$")
    floor: str | None = Field(default=None, max_length=60)
    landmark: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    estimated_hours: Decimal | None = Field(default=None, gt=0, le=24, max_digits=6, decimal_places=2)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)


class OrderUpdateRequest(BaseModel):
    """All fields optional — supervisor edits whatever needs adjusting."""

    service_id: UUID | None = None
    scheduled_date: date | None = None
    scheduled_slot: str | None = Field(default=None, min_length=2, max_length=60)
    street: str | None = Field(default=None, min_length=3, max_length=255)
    area: str | None = Field(default=None, min_length=2, max_length=120)
    city: str | None = Field(default=None, min_length=2, max_length=100)
    state: str | None = Field(default=None, min_length=2, max_length=100)
    pincode: str | None = Field(default=None, pattern=r"^\d{6}$")
    floor: str | None = Field(default=None, max_length=60)
    landmark: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    estimated_hours: Decimal | None = Field(default=None, gt=0, le=24, max_digits=6, decimal_places=2)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    customer_name: str | None = Field(default=None, min_length=2, max_length=120)
    customer_phone: str | None = Field(default=None, pattern=r"^\+?[1-9]\d{7,14}$")
    customer_email: EmailStr | None = None


class OrderStatusRequest(BaseModel):
    status: OrderStatus


class OrderAddonCreateRequest(BaseModel):
    addon_type: OrderAddonType
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    quantity: int = Field(default=1, ge=1, le=20)


class PaymentCreateRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    method: PaymentMethod = PaymentMethod.UPI
    status: PaymentStatus = PaymentStatus.RECEIVED
    reference: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=1000)


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #
class PaymentResponse(BaseModel):
    id: UUID
    amount: Decimal
    method: PaymentMethod
    status: PaymentStatus
    reference: str | None
    notes: str | None
    collected_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderAddonResponse(BaseModel):
    id: UUID
    addon_type: OrderAddonType
    price: Decimal
    quantity: int
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderEventResponse(BaseModel):
    id: UUID
    event_type: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderSummaryResponse(BaseModel):
    id: UUID
    order_code: str
    service_id: UUID
    service_name: str
    source: OrderSource
    status: OrderStatus
    customer_name: str
    customer_phone: str
    scheduled_date: date
    scheduled_slot: str
    estimated_hours: Decimal | None
    amount: Decimal | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderDetailResponse(BaseModel):
    id: UUID
    order_code: str
    service_id: UUID
    service_name: str
    source: OrderSource
    status: OrderStatus
    customer_name: str
    customer_phone: str
    customer_email: str | None
    street: str
    area: str
    city: str
    state: str
    pincode: str
    floor: str | None
    landmark: str | None
    scheduled_date: date
    scheduled_slot: str
    estimated_hours: Decimal | None
    amount: Decimal | None
    overtime_hours: Decimal | None
    description: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    payments: list[PaymentResponse]
    addons: list[OrderAddonResponse]
    events: list[OrderEventResponse]
    payment_status: str = "unpaid"
    payment_summary: str = "Unpaid"

    model_config = {"from_attributes": True}


class WhatsAppConfigResponse(BaseModel):
    id: int
    staff_group_link: str | None
    support_number: str

    model_config = {"from_attributes": True}


class WhatsAppConfigInput(BaseModel):
    staff_group_link: str | None = Field(default=None, max_length=500)
    support_number: str = Field(min_length=8, max_length=20)


class DayStatsResponse(BaseModel):
    date: date
    orders: int
    completed_orders: int
    revenue: Decimal
    revenue_upi: Decimal
    revenue_cash: Decimal
    by_source: dict[str, int]
    
    
    
# --------------------------------------------------------------------------- #
# Audit Log
# --------------------------------------------------------------------------- #
class AuditLogResponse(BaseModel):
    id: UUID
    actor_id: UUID | None
    action: str
    entity_type: str
    entity_id: str
    metadata_json: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# Staff / Cleaner Management
# --------------------------------------------------------------------------- #
class StaffCreateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(pattern=r"^\+?[1-9]\d{7,14}$")
    email: str | None = None
    specializations: str | None = None
    profile_image: str | None = None


class StaffUpdateRequest(BaseModel):
    full_name: str | None = None
    phone: str | None = Field(default=None, pattern=r"^\+?[1-9]\d{7,14}$")
    email: str | None = None
    status: str | None = None
    specializations: str | None = None
    profile_image: str | None = None
    rating: float | None = None


class StaffResponse(BaseModel):
    id: UUID
    full_name: str
    phone: str
    email: str | None
    status: str
    specializations: str | None
    profile_image: str | None
    rating: float | None
    total_jobs: int
    joined_at: datetime | None

    model_config = {"from_attributes": True}


class StaffAssignmentCreateRequest(BaseModel):
    staff_id: UUID
    role: str = "cleaner"
    notes: str | None = None


class StaffAssignmentResponse(BaseModel):
    id: UUID
    order_id: UUID
    staff_id: UUID
    staff_name: str | None = None
    assigned_by: UUID | None
    role: str
    started_at: datetime | None
    completed_at: datetime | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# Recurring Orders
# --------------------------------------------------------------------------- #
class RecurringOrderCreateRequest(BaseModel):
    customer_id: UUID
    service_id: UUID
    frequency: str = "weekly"
    preferred_day: str = Field(min_length=2, max_length=20)
    preferred_slot: str = Field(min_length=2, max_length=60)
    street: str = Field(min_length=3, max_length=255)
    area: str = Field(min_length=2, max_length=120)
    city: str = Field(default="Bhopal", min_length=2, max_length=100)
    state: str = Field(default="Madhya Pradesh", min_length=2, max_length=100)
    pincode: str = Field(pattern=r"^\d{6}$")
    floor: str | None = None
    landmark: str | None = None
    description: str | None = None
    estimated_hours: Decimal | None = None
    amount: Decimal | None = None
    end_date: date | None = None


class RecurringOrderUpdateRequest(BaseModel):
    frequency: str | None = None
    preferred_day: str | None = None
    preferred_slot: str | None = None
    is_active: bool | None = None
    estimated_hours: Decimal | None = None
    amount: Decimal | None = None
    end_date: date | None = None


class RecurringOrderResponse(BaseModel):
    id: UUID
    customer_id: UUID
    service_id: UUID
    service_name: str
    frequency: str
    preferred_day: str
    preferred_slot: str
    street: str
    area: str
    city: str
    state: str
    pincode: str
    floor: str | None
    landmark: str | None
    description: str | None
    estimated_hours: Decimal | None
    amount: Decimal | None
    is_active: bool
    next_date: date | None
    end_date: date | None

    model_config = {"from_attributes": True}