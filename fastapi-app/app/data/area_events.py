from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, func
from app.data.db import Base

class AreaEvent(Base):
    __tablename__ = "area_events"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, server_default=func.now())
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=False)
    track_id = Column(Integer, nullable=False)
    event = Column(String(20), nullable=False)
    dwell = Column(Float, default=0.0)