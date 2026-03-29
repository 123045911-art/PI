from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.area import Area
from app.models.heatmap_point import HeatmapPoint
from app.schemas.heatmap import HeatmapCreate, HeatmapListOut, HeatmapOut


def create_heatmap_point(db: Session, data: HeatmapCreate) -> HeatmapPoint:
    if data.area_id is not None:
        if not db.get(Area, data.area_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Área no encontrada.",
            )
    row = HeatmapPoint(
        timestamp=data.timestamp,
        area_id=data.area_id,
        track_id=data.track_id,
        cx=data.cx,
        cy=data.cy,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_heatmap_points(
    db: Session,
    *,
    area_id: int | None,
    date_from: datetime | None,
    date_to: datetime | None,
    skip: int,
    limit: int,
) -> HeatmapListOut:
    q = db.query(HeatmapPoint)
    if area_id is not None:
        q = q.filter(HeatmapPoint.area_id == area_id)
    if date_from is not None:
        q = q.filter(HeatmapPoint.timestamp >= date_from)
    if date_to is not None:
        q = q.filter(HeatmapPoint.timestamp <= date_to)

    total = q.count()
    rows = (
        q.order_by(HeatmapPoint.timestamp.desc()).offset(skip).limit(limit).all()
    )
    return HeatmapListOut(
        items=[HeatmapOut.model_validate(r) for r in rows],
        total=total,
    )
