from datetime import datetime

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    site_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    area_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    area_name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="watching")
    threshold_people: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schedule_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="all_days")
    schedule_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schedule_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    people_count_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
