from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.alert import AlertRead


class AnalysisRead(BaseModel):
    id: UUID
    dataset_id: UUID
    status: str
    config_json: dict[str, Any]
    metrics_json: dict[str, Any]
    notes_json: list[dict[str, Any]] = []
    created_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)

class AnalysisDetail(AnalysisRead):
    alerts: list[AlertRead]

class AnalystNoteCreate(BaseModel):
    episode_id: str | None = Field(default=None, max_length=120)
    narrative_cluster_id: str | None = Field(default=None, max_length=120)
    body: str = Field(min_length=1, max_length=4000)

class AnalystNote(AnalystNoteCreate):
    note_id: UUID
    created_at: datetime
