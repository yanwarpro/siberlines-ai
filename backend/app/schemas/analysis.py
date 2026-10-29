from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.alert import AlertRead


class AnalysisRead(BaseModel):
    id: UUID
    dataset_id: UUID
    status: str
    config_json: dict[str, Any]
    metrics_json: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AnalysisDetail(AnalysisRead):
    alerts: list[AlertRead]
