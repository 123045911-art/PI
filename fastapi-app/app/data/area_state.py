from sqlalchemy import Column, Integer, DateTime, ForeignKey, func
from app.data.db import Base

class AreaState(Base):
    __tablename__ = "area_state"
    area_id = Column(Integer, ForeignKey("areas.id"), primary_key=True)
    people_count = Column(Integer, nullable=False, default=0)
    last_update = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())