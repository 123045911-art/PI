from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AreaState(Base):
    __tablename__ = "area_state"

    area_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("areas.id", ondelete="CASCADE"), primary_key=True
    )
    people_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    last_update: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
