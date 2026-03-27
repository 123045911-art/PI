from sqlalchemy import Column, Integer, DateTime, ForeignKey, func
from app.data.db import Base

class HeatmapPoint(Base):
    __tablename__ = "heatmap_points"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, server_default=func.now())
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=True)
    track_id = Column(Integer, nullable=False)
    cx = Column(Integer, nullable=False)
    cy = Column(Integer, nullable=False)