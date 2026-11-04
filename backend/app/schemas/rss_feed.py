from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class RssFeedCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: HttpUrl

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("url")
    @classmethod
    def require_https(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("RSS feed URLs must use HTTPS")
        if len(str(value)) > 512:
            raise ValueError("RSS feed URLs cannot exceed 512 characters")
        if value.port not in (None, 443):
            raise ValueError("RSS feed URLs must use the standard HTTPS port")
        if value.username or value.password:
            raise ValueError("RSS feed URLs must not contain credentials")
        return value


class RssFeedUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    url: HttpUrl | None = None
    enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("url")
    @classmethod
    def require_https(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is None:
            return None
        if value.scheme != "https":
            raise ValueError("RSS feed URLs must use HTTPS")
        if len(str(value)) > 512:
            raise ValueError("RSS feed URLs cannot exceed 512 characters")
        if value.port not in (None, 443):
            raise ValueError("RSS feed URLs must use the standard HTTPS port")
        if value.username or value.password:
            raise ValueError("RSS feed URLs must not contain credentials")
        return value


class RssFeedRead(BaseModel):
    id: UUID
    name: str
    url: str
    enabled: bool
    dataset_id: UUID | None
    dataset_name: str | None = None
    row_count: int = 0
    last_synced_at: datetime | None
    last_sync_status: str | None
    last_sync_error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RssSyncResult(BaseModel):
    feed_id: UUID
    dataset_id: UUID
    items_received: int
    items_inserted: int
    duplicates_skipped: int
    invalid_items: int
    synced_at: datetime


class RssSyncRunRead(BaseModel):
    id: UUID
    trigger_type: str
    status: str
    source_feed_id: UUID | None
    source_name: str | None
    started_at: datetime
    completed_at: datetime | None
    total_sources: int
    successful_sources: int
    failed_sources: int
    items_received: int
    new_articles: int
    duplicate_articles: int
    invalid_articles: int
    error_summary: str | None

    model_config = ConfigDict(from_attributes=True)


class RssSyncStatus(BaseModel):
    schedule_enabled: bool
    schedule_interval_minutes: int
    next_scheduled_at: datetime | None
    latest_run: RssSyncRunRead | None
