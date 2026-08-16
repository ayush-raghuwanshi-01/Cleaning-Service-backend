from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

import jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext

from app.core.config import Settings

password_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def create_token(subject: UUID, token_type: str, expires_delta: timedelta, secret: str) -> str:
    now = datetime.now(UTC)
    return jwt.encode({"sub": str(subject), "type": token_type, "iat": now, "exp": now + expires_delta}, secret, algorithm="HS256")


def create_access_token(user_id: UUID, settings: Settings) -> str:
    return create_token(user_id, "access", timedelta(minutes=settings.access_token_expire_minutes), settings.jwt_secret_key)


def create_refresh_token(user_id: UUID, settings: Settings) -> str:
    return create_token(user_id, "refresh", timedelta(days=settings.refresh_token_expire_days), settings.jwt_refresh_secret_key)


def decode_token(token: str, expected_type: str, secret: str) -> UUID:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        if payload.get("type") != expected_type:
            raise ValueError("Unexpected token type")
        return UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc


def token_fingerprint(token: str) -> str:
    return sha256(token.encode()).hexdigest()
