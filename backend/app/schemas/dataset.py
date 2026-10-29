from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DatasetRead(BaseModel):
    id: int
    name: str
    source: str
    status: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetSummary(BaseModel):
    id: int
    name: str
    source: str
    status: str
    created_at: datetime
    updated_at: datetime
    post_count: int
