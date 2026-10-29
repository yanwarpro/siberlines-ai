from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DatasetRead(BaseModel):
    id: UUID
    name: str
    source_type: str
    status: str
    row_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetSummary(BaseModel):
    id: UUID
    name: str
    source_type: str
    status: str
    created_at: datetime
    row_count: int
