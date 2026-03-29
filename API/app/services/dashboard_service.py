from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.area import Area
from app.models.area_event import AreaEvent
from app.models.area_state import AreaState
from app.models.heatmap_point import HeatmapPoint
from app.schemas.dashboard import (
    DashboardAreaRow,
    DashboardAreasOut,
    DashboardEventRow,
    DashboardEventsOut,
    DashboardHeatmapOut,
    DashboardSummary,
)
from app.schemas.heatmap import HeatmapOut


def get_summary(db: Session) -> DashboardSummary:
    total_people = (
        db.query(func.coalesce(func.sum(AreaState.people_count), 0)).scalar() or 0
    )
    total_entries = (
        db.query(func.count(AreaEvent.id))
        .filter(func.lower(AreaEvent.event) == "enter")
        .scalar()
        or 0
    )
    total_exits = (
        db.query(func.count(AreaEvent.id))
        .filter(func.lower(AreaEvent.event) == "exit")
        .scalar()
        or 0
    )
    areas_count = db.query(func.count(Area.id)).scalar() or 0

    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
    events_last_24h = (
        db.query(func.count(AreaEvent.id)).filter(AreaEvent.timestamp >= since).scalar()
        or 0
    )

    return DashboardSummary(
        total_people=int(total_people),
        total_entries=int(total_entries),
        total_exits=int(total_exits),
        areas_count=int(areas_count),
        events_last_24h=int(events_last_24h),
    )


def get_areas_dashboard(db: Session) -> DashboardAreasOut:
    rows = (
        db.query(Area, AreaState)
        .outerjoin(AreaState, AreaState.area_id == Area.id)
        .order_by(Area.id)
        .all()
    )
    items: list[DashboardAreaRow] = []
    for area, st in rows:
        items.append(
            DashboardAreaRow(
                area_id=area.id,
                name=area.name,
                x1=area.x1,
                y1=area.y1,
                x2=area.x2,
                y2=area.y2,
                people_count=st.people_count if st else 0,
                last_update=st.last_update if st else None,
            )
        )
    return DashboardAreasOut(items=items)


def get_events_dashboard(
    db: Session, *, skip: int, limit: int, area_id: int | None
) -> DashboardEventsOut:
    base = db.query(AreaEvent).join(Area, Area.id == AreaEvent.area_id)
    if area_id is not None:
        base = base.filter(AreaEvent.area_id == area_id)
    total = base.count()

    q = (
        db.query(AreaEvent, Area.name)
        .join(Area, Area.id == AreaEvent.area_id)
        .order_by(AreaEvent.timestamp.desc())
    )
    if area_id is not None:
        q = q.filter(AreaEvent.area_id == area_id)
    result = q.offset(skip).limit(limit).all()
    items = [
        DashboardEventRow(
            id=ev.id,
            timestamp=ev.timestamp,
            area_id=ev.area_id,
            area_name=name,
            track_id=ev.track_id,
            event=ev.event,
            dwell=float(ev.dwell),
        )
        for ev, name in result
    ]
    return DashboardEventsOut(
        items=items, total=int(total), skip=skip, limit=limit
    )


def get_heatmap_dashboard(
    db: Session,
    *,
    area_id: int | None,
    date_from: datetime | None,
    date_to: datetime | None,
    limit: int,
) -> DashboardHeatmapOut:
    q = db.query(HeatmapPoint)
    if area_id is not None:
        q = q.filter(HeatmapPoint.area_id == area_id)
    if date_from is not None:
        q = q.filter(HeatmapPoint.timestamp >= date_from)
    if date_to is not None:
        q = q.filter(HeatmapPoint.timestamp <= date_to)

    total = q.count()
    rows = q.order_by(HeatmapPoint.timestamp.desc()).limit(limit).all()
    return DashboardHeatmapOut(
        items=[HeatmapOut.model_validate(r) for r in rows],
        total=total,
    )
