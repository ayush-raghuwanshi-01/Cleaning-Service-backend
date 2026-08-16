from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ServiceAreaInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    pincode: str = Field(pattern=r"^\d{6}$")
    is_active: bool = True


class ServiceAreaResponse(ServiceAreaInput):
    id: UUID
    model_config = {"from_attributes": True}


class ServiceInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    base_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    duration_minutes: int = Field(gt=0, le=1440)
    is_active: bool = True


class ServiceResponse(ServiceInput):
    id: UUID
    model_config = {"from_attributes": True}


class AddonInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    duration_minutes: int = Field(default=0, ge=0, le=1440)
    is_active: bool = True


class AddonResponse(AddonInput):
    id: UUID
    service_id: UUID
    model_config = {"from_attributes": True}


class AddressInput(BaseModel):
    label: str = Field(min_length=2, max_length=60)
    recipient_name: str = Field(min_length=2, max_length=120)
    recipient_phone: str = Field(pattern=r"^\+?[1-9]\d{7,14}$")
    line1: str = Field(min_length=3, max_length=255)
    line2: str | None = Field(default=None, max_length=255)
    landmark: str | None = Field(default=None, max_length=160)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    pincode: str = Field(pattern=r"^\d{6}$")
    is_default: bool = False


class AddressResponse(AddressInput):
    id: UUID
    service_area_id: UUID | None
    model_config = {"from_attributes": True}
