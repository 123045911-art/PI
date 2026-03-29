from datetime import datetime

from pydantic import BaseModel

from app.schemas.heatmap import HeatmapOut


class DashboardSummary(BaseModel):
    total_people: int
    total_entries: int
    total_exits: int
    areas_count: int
    events_last_24h: int


class DashboardAreaRow(BaseModel):
    area_id: int
    name: str
    x1: int
    y1: int
    x2: int
    y2: int
    people_count: int
    last_update: datetime | None


class DashboardAreasOut(BaseModel):
    items: list[DashboardAreaRow]


class DashboardEventRow(BaseModel):
    id: int
    timestamp: datetime
    area_id: int
    area_name: str | None
    track_id: int
    event: str
    dwell: float


class DashboardEventsOut(BaseModel):
    items: list[DashboardEventRow]
    total: int
    skip: int
    limit: int


class DashboardHeatmapOut(BaseModel):
    items: list[HeatmapOut]
    total: int
