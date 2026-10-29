from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AlertRead(BaseModel):
    id: int
    dataset_id: int | None
    post_id: int | None
    title: str
    description: str | None
    severity: str
    status: str
    details: dict[str, Any] | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
