from pydantic import BaseModel, Field

class AreaState(BaseModel):
    area_id: int
    people_count: int = Field(default=0, ge=0)