from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update

from app.api.deps import DbSession, get_current_user, require_operations
from app.models.business import Address, Service, ServiceAddon, ServiceArea
from app.models.user import AuditLog, User
from app.schemas.business import AddonInput, AddonResponse, AddressInput, AddressResponse, ServiceAreaInput, ServiceAreaResponse, ServiceInput, ServiceResponse

public_router = APIRouter(tags=["catalog"])
customer_router = APIRouter(prefix="/addresses", tags=["addresses"])
admin_router = APIRouter(prefix="/admin", tags=["administration"])


@public_router.get("/services", response_model=list[ServiceResponse])
async def list_services(session: DbSession) -> list[Service]:
    return list((await session.scalars(select(Service).where(Service.is_active.is_(True)).order_by(Service.name))).all())


@public_router.get("/service-areas", response_model=list[ServiceAreaResponse])
async def list_service_areas(session: DbSession) -> list[ServiceArea]:
    return list((await session.scalars(select(ServiceArea).where(ServiceArea.is_active.is_(True)).order_by(ServiceArea.name))).all())


@customer_router.get("", response_model=list[AddressResponse])
async def list_addresses(session: DbSession, user: Annotated[User, Depends(get_current_user)]) -> list[Address]:
    return list((await session.scalars(select(Address).where(Address.user_id == user.id).order_by(Address.is_default.desc(), Address.created_at.desc()))).all())


@customer_router.post("", response_model=AddressResponse, status_code=status.HTTP_201_CREATED)
async def create_address(payload: AddressInput, session: DbSession, user: Annotated[User, Depends(get_current_user)]) -> Address:
    area = await session.scalar(select(ServiceArea).where(ServiceArea.pincode == payload.pincode, ServiceArea.is_active.is_(True)))
    if payload.is_default:
        await session.execute(update(Address).where(Address.user_id == user.id).values(is_default=False))
    address = Address(user_id=user.id, service_area_id=area.id if area else None, **payload.model_dump())
    session.add(address)
    session.add(AuditLog(actor_id=user.id, action="address_created", entity_type="address", entity_id=str(address.id)))
    await session.commit()
    await session.refresh(address)
    return address


@customer_router.patch("/{address_id}", response_model=AddressResponse)
async def update_address(address_id: UUID, payload: AddressInput, session: DbSession, user: Annotated[User, Depends(get_current_user)]) -> Address:
    address = await session.scalar(select(Address).where(Address.id == address_id, Address.user_id == user.id))
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    area = await session.scalar(select(ServiceArea).where(ServiceArea.pincode == payload.pincode, ServiceArea.is_active.is_(True)))
    if payload.is_default:
        await session.execute(update(Address).where(Address.user_id == user.id, Address.id != address_id).values(is_default=False))
    for name, value in payload.model_dump().items():
        setattr(address, name, value)
    address.service_area_id = area.id if area else None
    session.add(AuditLog(actor_id=user.id, action="address_updated", entity_type="address", entity_id=str(address.id)))
    await session.commit()
    await session.refresh(address)
    return address


@customer_router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(address_id: UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]) -> None:
    address = await session.scalar(select(Address).where(Address.id == address_id, Address.user_id == user.id))
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    await session.delete(address)
    session.add(AuditLog(actor_id=user.id, action="address_deleted", entity_type="address", entity_id=str(address_id)))
    await session.commit()


@admin_router.post("/service-areas", response_model=ServiceAreaResponse, status_code=status.HTTP_201_CREATED)
async def create_service_area(payload: ServiceAreaInput, session: DbSession, actor: Annotated[User, Depends(require_operations)]) -> ServiceArea:
    area = ServiceArea(**payload.model_dump())
    session.add(area)
    session.add(AuditLog(actor_id=actor.id, action="service_area_created", entity_type="service_area", entity_id=str(area.id)))
    await session.commit()
    await session.refresh(area)
    return area


@admin_router.post("/services", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(payload: ServiceInput, session: DbSession, actor: Annotated[User, Depends(require_operations)]) -> Service:
    service = Service(**payload.model_dump())
    session.add(service)
    session.add(AuditLog(actor_id=actor.id, action="service_created", entity_type="service", entity_id=str(service.id)))
    await session.commit()
    await session.refresh(service)
    return service


@admin_router.post("/services/{service_id}/addons", response_model=AddonResponse, status_code=status.HTTP_201_CREATED)
async def create_addon(service_id: UUID, payload: AddonInput, session: DbSession, actor: Annotated[User, Depends(require_operations)]) -> ServiceAddon:
    if not await session.get(Service, service_id):
        raise HTTPException(status_code=404, detail="Service not found")
    addon = ServiceAddon(service_id=service_id, **payload.model_dump())
    session.add(addon)
    session.add(AuditLog(actor_id=actor.id, action="service_addon_created", entity_type="service_addon", entity_id=str(addon.id)))
    await session.commit()
    await session.refresh(addon)
    return addon


@admin_router.get("/services", response_model=list[ServiceResponse])
async def admin_list_services(session: DbSession, actor: Annotated[User, Depends(require_operations)]) -> list[Service]:
    return list((await session.scalars(select(Service).order_by(Service.name))).all())


@admin_router.patch("/services/{service_id}", response_model=ServiceResponse)
async def update_service(service_id: UUID, payload: ServiceInput, session: DbSession, actor: Annotated[User, Depends(require_operations)]) -> Service:
    service = await session.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    for name, value in payload.model_dump().items():
        setattr(service, name, value)
    session.add(AuditLog(actor_id=actor.id, action="service_updated", entity_type="service", entity_id=str(service.id)))
    await session.commit()
    await session.refresh(service)
    return service


@admin_router.get("/service-areas", response_model=list[ServiceAreaResponse])
async def admin_list_service_areas(session: DbSession, actor: Annotated[User, Depends(require_operations)]) -> list[ServiceArea]:
    return list((await session.scalars(select(ServiceArea).order_by(ServiceArea.name))).all())


@admin_router.patch("/service-areas/{area_id}", response_model=ServiceAreaResponse)
async def update_service_area(area_id: UUID, payload: ServiceAreaInput, session: DbSession, actor: Annotated[User, Depends(require_operations)]) -> ServiceArea:
    area = await session.get(ServiceArea, area_id)
    if not area:
        raise HTTPException(status_code=404, detail="Service area not found")
    for name, value in payload.model_dump().items():
        setattr(area, name, value)
    session.add(AuditLog(actor_id=actor.id, action="service_area_updated", entity_type="service_area", entity_id=str(area.id)))
    await session.commit()
    await session.refresh(area)
    return area