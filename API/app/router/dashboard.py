from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.data.db import get_db
from app.schemas.dashboard import (
    DashboardAreasOut,
    DashboardEventsOut,
    DashboardHeatmapOut,
    DashboardSummary,
)
from app.security.auth import get_current_user
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary, dependencies=[Depends(get_current_user)])
def dashboard_summary(db: Session = Depends(get_db)):
    return dashboard_service.get_summary(db)


@router.get("/areas", response_model=DashboardAreasOut, dependencies=[Depends(get_current_user)])
def dashboard_areas(db: Session = Depends(get_db)):
    return dashboard_service.get_areas_dashboard(db)


@router.get("/events", response_model=DashboardEventsOut, dependencies=[Depends(get_current_user)])
def dashboard_events(
    db: Session = Depends(get_db),
    area_id: int | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
):
    return dashboard_service.get_events_dashboard(
        db, skip=skip, limit=limit, area_id=area_id
    )


@router.get("/heatmap", response_model=DashboardHeatmapOut, dependencies=[Depends(get_current_user)])
def dashboard_heatmap(
    db: Session = Depends(get_db),
    area_id: int | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
):
    return dashboard_service.get_heatmap_dashboard(
        db,
        area_id=area_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )

