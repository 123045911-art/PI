from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.data.db import get_db
from app.schemas.heatmap import HeatmapCreate, HeatmapListOut, HeatmapOut
from app.services import heatmap_service

router = APIRouter(prefix="/heatmap", tags=["heatmap"])


@router.post("", response_model=HeatmapOut, status_code=status.HTTP_201_CREATED)
def create_heatmap_point(payload: HeatmapCreate, db: Session = Depends(get_db)):
    return heatmap_service.create_heatmap_point(db, payload)


@router.get("", response_model=HeatmapListOut)
def list_heatmap_points(
    db: Session = Depends(get_db),
    area_id: int | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    return heatmap_service.list_heatmap_points(
        db,
        area_id=area_id,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
