from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AlertRead(BaseModel):
    id: UUID
    analysis_id: UUID
    narrative_key: str
    severity: str
    baseline_count: int
    observed_count: int
    evidence_json: list[Any]
    explanation: str | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
