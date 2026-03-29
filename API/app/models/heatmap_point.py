from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class HeatmapPoint(Base):
    __tablename__ = "heatmap_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    area_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("areas.id", ondelete="SET NULL"), nullable=True
    )
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    cx: Mapped[int] = mapped_column(Integer, nullable=False)
    cy: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
