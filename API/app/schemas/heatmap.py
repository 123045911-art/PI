from datetime import datetime

from pydantic import BaseModel, Field


class HeatmapCreate(BaseModel):
    track_id: int
    cx: int
    cy: int
    timestamp: datetime
    area_id: int | None = None


class HeatmapOut(BaseModel):
    id: int
    timestamp: datetime
    area_id: int | None
    track_id: int
    cx: int
    cy: int
    created_at: datetime

    model_config = {"from_attributes": True}


class HeatmapListOut(BaseModel):
    items: list[HeatmapOut]
    total: int
