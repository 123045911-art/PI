from pydantic import BaseModel, Field
from typing import Optional

class HeatmapPoint(BaseModel):
    area_id: Optional[int] = None
    track_id: int
    cx: int
    cy: int