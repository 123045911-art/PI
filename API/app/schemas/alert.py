from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

AlertType = Literal["crowding", "low_flow", "unusual_dwell", "blocked_access", "manual"]
AlertStatus = Literal["new", "watching", "triggered", "acknowledged", "resolved"]
ScheduleMode = Literal["immediate", "all_days", "weekly", "date"]


def validate_date_text(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("La fecha debe ser real y usar el formato AAAA-MM-DD.") from exc
    return value


def validate_schedule(model):
    if model.schedule_mode == "weekly" and model.schedule_day is None:
        raise ValueError("Selecciona un día para la alerta semanal.")
    if model.schedule_mode == "date":
        if model.schedule_date is None:
            raise ValueError("Escribe la fecha específica de la alerta.")
        if date.fromisoformat(model.schedule_date) < date.today():
            raise ValueError("La fecha específica debe ser hoy o un día futuro.")
    if model.type in {"crowding", "low_flow"} and model.threshold_people is None:
        raise ValueError("El umbral de personas es obligatorio para esta alerta.")
    return model


class AlertBase(BaseModel):
    area_id: str = Field(alias="areaId", min_length=1, max_length=100)
    area_name: str = Field(alias="areaName", min_length=1, max_length=100)
    type: AlertType
    reason: str = Field(default="", max_length=500)
    status: AlertStatus = "watching"
    threshold_people: int | None = Field(default=None, alias="thresholdPeople", ge=1, le=120)
    schedule_mode: ScheduleMode = Field(default="all_days", alias="scheduleMode")
    schedule_day: int | None = Field(default=None, alias="scheduleDay", ge=0, le=6)
    schedule_date: str | None = Field(default=None, alias="scheduleDate", max_length=10)
    people_count_snapshot: int = Field(default=0, alias="peopleCountSnapshot", ge=0)
    created_by: str = Field(default="operador", alias="createdBy", min_length=1, max_length=50)

    model_config = {"populate_by_name": True}
    _date_format = field_validator("schedule_date")(validate_date_text)


class AlertCreate(AlertBase):
    id: str | None = Field(default=None, max_length=64)
    created_at: datetime | None = Field(default=None, alias="createdAt")

    _valid_combination = model_validator(mode="after")(validate_schedule)


class AlertUpdate(BaseModel):
    area_id: str | None = Field(default=None, alias="areaId", min_length=1, max_length=100)
    area_name: str | None = Field(default=None, alias="areaName", min_length=1, max_length=100)
    type: AlertType | None = None
    reason: str | None = Field(default=None, max_length=500)
    status: AlertStatus | None = None
    threshold_people: int | None = Field(default=None, alias="thresholdPeople", ge=1, le=120)
    schedule_mode: ScheduleMode | None = Field(default=None, alias="scheduleMode")
    schedule_day: int | None = Field(default=None, alias="scheduleDay", ge=0, le=6)
    schedule_date: str | None = Field(default=None, alias="scheduleDate", max_length=10)
    people_count_snapshot: int | None = Field(default=None, alias="peopleCountSnapshot", ge=0)

    model_config = {"populate_by_name": True}
    _date_format = field_validator("schedule_date")(validate_date_text)

    @model_validator(mode="after")
    def valid_combination(self):
        if self.schedule_mode == "weekly" and self.schedule_day is None:
            raise ValueError("Selecciona un día para la alerta semanal.")
        if self.schedule_mode == "date":
            if self.schedule_date is None:
                raise ValueError("Escribe la fecha específica de la alerta.")
            if date.fromisoformat(self.schedule_date) < date.today():
                raise ValueError("La fecha específica debe ser hoy o un día futuro.")
        if self.type in {"crowding", "low_flow"} and self.threshold_people is None:
            raise ValueError("El umbral de personas es obligatorio para esta alerta.")
        return self


class AlertOut(AlertBase):
    id: str
    site_id: str = Field(alias="siteId")
    created_at: datetime = Field(alias="createdAt")

    model_config = {"populate_by_name": True, "from_attributes": True}


class AlertListOut(BaseModel):
    items: list[AlertOut]


class AlertItemOut(BaseModel):
    item: AlertOut
