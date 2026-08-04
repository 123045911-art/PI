from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


def normalized_area_name(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("El nombre del área es obligatorio.")
    return value


class AreaCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    x1: int = Field(..., ge=0)
    y1: int = Field(..., ge=0)
    x2: int = Field(..., ge=0)
    y2: int = Field(..., ge=0)

    _name = field_validator("name")(normalized_area_name)

    @model_validator(mode="after")
    def valid_rectangle(self):
        if self.x1 == self.x2 or self.y1 == self.y2:
            raise ValueError("El rectángulo del área debe tener ancho y alto mayores que cero.")
        return self


class AreaUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    x1: int | None = Field(None, ge=0)
    y1: int | None = Field(None, ge=0)
    x2: int | None = Field(None, ge=0)
    y2: int | None = Field(None, ge=0)

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str | None) -> str | None:
        return normalized_area_name(value) if value is not None else None


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
