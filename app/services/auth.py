from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, token_fingerprint, verify_password
from app.models.user import AuditLog, RefreshSession, User, UserRole
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


async def register_customer(session: AsyncSession, payload: RegisterRequest) -> User:
    conditions = [User.phone == payload.phone]
    if payload.email:
        conditions.append(User.email == payload.email.lower())
    result = await session.execute(select(User).where(or_(*conditions)))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone number or email already registered")
    user = User(full_name=payload.full_name, phone=payload.phone, email=payload.email.lower() if payload.email else None, password_hash=hash_password(payload.password), role=UserRole.CUSTOMER)
    session.add(user)
    await session.flush()
    session.add(AuditLog(actor_id=user.id, action="customer_registered", entity_type="user", entity_id=str(user.id)))
    await session.commit()
    await session.refresh(user)
    return user


async def issue_tokens(session: AsyncSession, user: User, settings: Settings) -> TokenResponse:
    access_token = create_access_token(user.id, settings)
    refresh_token = create_refresh_token(user.id, settings)
    session.add(RefreshSession(user_id=user.id, token_hash=token_fingerprint(refresh_token), expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)))
    session.add(AuditLog(actor_id=user.id, action="login", entity_type="user", entity_id=str(user.id)))
    await session.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


async def login(session: AsyncSession, payload: LoginRequest, settings: Settings) -> TokenResponse:
    result = await session.execute(select(User).where(or_(User.phone == payload.identifier, User.email == payload.identifier.lower())))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    return await issue_tokens(session, user, settings)


async def refresh_tokens(session: AsyncSession, refresh_token: str, settings: Settings) -> TokenResponse:
    user_id = decode_token(refresh_token, "refresh", settings.jwt_refresh_secret_key)
    result = await session.execute(
        select(RefreshSession).where(
            RefreshSession.token_hash == token_fingerprint(refresh_token),
            RefreshSession.user_id == user_id,
            RefreshSession.revoked_at.is_(None),
            RefreshSession.expires_at > datetime.now(UTC),
        ).with_for_update()
    )
    token_session = result.scalar_one_or_none()
    user = await session.get(User, user_id)
    if not token_session or not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    token_session.revoked_at = datetime.now(UTC)
    session.add(AuditLog(actor_id=user.id, action="token_rotated", entity_type="refresh_session", entity_id=str(token_session.id)))
    return await issue_tokens(session, user, settings)


async def logout(session: AsyncSession, refresh_token: str, settings: Settings) -> None:
    user_id = decode_token(refresh_token, "refresh", settings.jwt_refresh_secret_key)
    result = await session.execute(
        select(RefreshSession).where(
            RefreshSession.token_hash == token_fingerprint(refresh_token),
            RefreshSession.user_id == user_id,
            RefreshSession.revoked_at.is_(None),
        ).with_for_update()
    )
    token_session = result.scalar_one_or_none()
    if token_session:
        token_session.revoked_at = datetime.now(UTC)
        session.add(AuditLog(actor_id=user_id, action="logout", entity_type="refresh_session", entity_id=str(token_session.id)))
        await session.commit()
