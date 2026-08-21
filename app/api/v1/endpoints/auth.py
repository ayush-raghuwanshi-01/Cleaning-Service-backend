from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import DbSession, get_current_user
from app.core.config import Settings, get_settings
from app.middleware.rate_limit import limiter
from app.models.user import User
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth import login, logout, refresh_tokens, register_customer

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, payload: RegisterRequest, session: DbSession) -> User:
    return await register_customer(session, payload)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def sign_in(request: Request, payload: LoginRequest, session: DbSession, settings: Annotated[Settings, Depends(get_settings)]) -> TokenResponse:
    return await login(session, payload, settings)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh(request: Request, payload: RefreshRequest, session: DbSession, settings: Annotated[Settings, Depends(get_settings)]) -> TokenResponse:
    return await refresh_tokens(session, payload.refresh_token, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out(payload: LogoutRequest, session: DbSession, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    await logout(session, payload.refresh_token, settings)


@router.get("/me", response_model=UserResponse)
async def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user