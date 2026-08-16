from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import decode_token
from app.db.session import get_db_session
from app.models.user import User, UserRole

bearer = HTTPBearer(auto_error=False)
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_user(session: DbSession, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)], settings: Annotated[Settings, Depends(get_settings)]) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id: UUID = decode_token(credentials.credentials, "access", settings.jwt_secret_key)
    user = await session.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


def require_roles(*roles: UserRole) -> Callable:
    async def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return dependency


require_customer = require_roles(UserRole.CUSTOMER)
require_staff = require_roles(UserRole.STAFF)
require_operations = require_roles(UserRole.OPERATIONS, UserRole.ADMIN, UserRole.OWNER)
require_admin = require_roles(UserRole.ADMIN, UserRole.OWNER)
require_owner = require_roles(UserRole.OWNER)
