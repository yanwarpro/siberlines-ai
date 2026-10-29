from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AnalysisRead(BaseModel):
    id: int
    dataset_id: int | None
    post_id: int | None
    analysis_type: str
    status: str
    result: dict[str, Any] | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
