from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AnalysisRead(BaseModel):
    id: UUID
    dataset_id: UUID
    status: str
    config_json: dict[str, Any]
    metrics_json: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
