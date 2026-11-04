from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.security import parse_cors_origins, validate_cors_origins

ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    database_url: str
    cors_origins: list[str] = ["http://localhost:5173"]
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    rss_sync_secret: SecretStr | None = None
    rss_sync_schedule_enabled: bool = False

    model_config = SettingsConfigDict(
        env_file=ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        enable_decoding=False,
        extra="ignore",
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use PostgreSQL")
        return value

    @field_validator("supabase_url")
    @classmethod
    def validate_supabase_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("SUPABASE_URL must be an HTTPS origin on the standard port")
        return value.rstrip("/")

    @field_validator("rss_sync_secret", mode="before")
    @classmethod
    def validate_rss_sync_secret(cls, value: object) -> object:
        if value is None or value == "":
            return None
        secret = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        if len(secret) < 32:
            raise ValueError("RSS_SYNC_SECRET must contain at least 32 characters")
        return value

    @model_validator(mode="after")
    def require_secret_for_enabled_schedule(self) -> "Settings":
        if self.rss_sync_schedule_enabled and self.rss_sync_secret is None:
            raise ValueError(
                "RSS_SYNC_SECRET is required when RSS_SYNC_SCHEDULE_ENABLED is true"
            )
        return self

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        return parse_cors_origins(value)

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        return validate_cors_origins(origins)


@lru_cache
def get_settings() -> Settings:
    return Settings()
