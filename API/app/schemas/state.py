from datetime import datetime

from pydantic import BaseModel


class AreaStateOut(BaseModel):
    area_id: int
    people_count: int
    last_update: datetime | None = None

    model_config = {"from_attributes": True}


class StateListOut(BaseModel):
    items: list[AreaStateOut]
    total_people: int
