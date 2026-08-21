from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    environment: str = "development"
    database_url: str
    jwt_secret_key: str = Field(min_length=32)
    jwt_refresh_secret_key: str = Field(min_length=32)
    cors_origins: list[str] = ["http://localhost:5173"]
    access_token_expire_minutes: int = Field(default=15, gt=0)
    refresh_token_expire_days: int = Field(default=30, gt=0)
    log_level: str = "INFO"
    bootstrap_owner_name: str | None = None
    bootstrap_owner_phone: str | None = None
    bootstrap_owner_email: str | None = None
    bootstrap_owner_password: str | None = None

    # Rate limiting
    rate_limit_auth: str = "10/minute"
    rate_limit_general: str = "120/minute"


@lru_cache
def get_settings() -> Settings:
    return Settings()