from sqlalchemy import Column, Integer, String, DateTime, TIMESTAMP, func
from app.data.db import Base

class Area(Base):
    __tablename__ = "areas"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    x1 = Column(Integer, nullable=False)
    y1 = Column(Integer, nullable=False)
    x2 = Column(Integer, nullable=False)
    y2 = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())