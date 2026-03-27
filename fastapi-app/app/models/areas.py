from pydantic import BaseModel, Field

class Area(BaseModel):
    name: str = Field(..., max_length=100)
    x1: int
    y1: int
    x2: int
    y2: int