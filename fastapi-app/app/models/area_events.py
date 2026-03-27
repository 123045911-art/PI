from pydantic import BaseModel, Field

class AreaEvents(BaseModel):
    area_id: int
    track_id: int
    event: str = Field(..., pattern="^(enter|exit)$")
    dwell: float = 0.0
