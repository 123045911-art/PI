from datetime import datetime

from pydantic import BaseModel, Field


class AreaCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    x1: int
    y1: int
    x2: int
    y2: int


class AreaUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    x1: int | None = None
    y1: int | None = None
    x2: int | None = None
    y2: int | None = None


class AreaOut(BaseModel):
    id: int
    name: str
    x1: int
    y1: int
    x2: int
    y2: int
    people_count: int = 0
    last_update: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
