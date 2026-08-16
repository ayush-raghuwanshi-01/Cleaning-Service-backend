from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import DbSession, get_current_user
from app.core.config import Settings, get_settings
from app.models.user import User
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth import login, logout, refresh_tokens, register_customer

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: DbSession) -> User:
    return await register_customer(session, payload)


@router.post("/login", response_model=TokenResponse)
async def sign_in(payload: LoginRequest, session: DbSession, settings: Annotated[Settings, Depends(get_settings)]) -> TokenResponse:
    return await login(session, payload, settings)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, session: DbSession, settings: Annotated[Settings, Depends(get_settings)]) -> TokenResponse:
    return await refresh_tokens(session, payload.refresh_token, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out(payload: LogoutRequest, session: DbSession, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    await logout(session, payload.refresh_token, settings)


@router.get("/me", response_model=UserResponse)
async def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
