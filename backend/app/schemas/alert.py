from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

AlertStatus = Literal[
    "new",
    "pending_review",
    "under_review",
    "resolved",
    "dismissed",
]

def _as_utc(value: Any) -> Any:
    """Guarantee an explicit UTC offset.

    Postgres ``timestamptz`` round-trips the offset, but SQLite (used by the test
    suite) drops it, and legacy rows may hold naive values. Analysts must never
    see a timestamp whose timezone is implicit, so naive values are declared UTC.
    """
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value

class AlertRead(BaseModel):
    id: UUID
    analysis_id: UUID
    dataset_id: UUID | None = None
    narrative_key: str
    narrative_cluster_id: str | None = None
    episode_id: str | None = None
    severity: str
    baseline_count: int
    observed_count: int
    evidence_json: list[Any]
    explanation: str | None
    status: str
    detection_interval_start: datetime | None = None
    detection_interval_end: datetime | None = None
    detected_at: datetime | None = None
    fingerprint: str | None = None
    status_history_json: list[Any] = []
    analyst_notes_json: list[Any] = []
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    _normalise_utc = field_validator(
        "detection_interval_start",
        "detection_interval_end",
        "detected_at",
        "created_at",
        "updated_at",
        mode="before",
    )(_as_utc)

class AlertListItem(AlertRead):
    dataset_name: str | None = None
    analysis_created_at: datetime | None = None

    _normalise_analysis_utc = field_validator(
        "analysis_created_at", mode="before"
    )(_as_utc)

class AlertDetail(AlertListItem):
    pass

class AlertSummary(BaseModel):
    total: int
    new: int
    pending_review: int
    under_review: int
    resolved: int
    dismissed: int
    high_priority: int
    medium_priority: int
    open_total: int

class AlertStatusUpdate(BaseModel):
    status: AlertStatus
    note: str | None = Field(default=None, max_length=2000)

class AlertNoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

class AlertNote(BaseModel):
    note_id: UUID
    body: str
    created_at: datetime

    _normalise_utc = field_validator("created_at", mode="before")(_as_utc)

class AlertListPage(BaseModel):
    items: list[AlertListItem]
    total: int
    limit: int
    offset: int
