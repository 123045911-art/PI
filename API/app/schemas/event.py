from datetime import datetime

from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    area_id: int
    track_id: int
    event: str = Field(..., min_length=1, max_length=20)
    timestamp: datetime
    dwell: float = 0.0


class EventOut(BaseModel):
    id: int
    timestamp: datetime
    area_id: int
    track_id: int
    event: str
    dwell: float
    created_at: datetime

    model_config = {"from_attributes": True}
