from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.area import Area
from app.models.area_event import AreaEvent
from app.models.area_state import AreaState
from app.schemas.event import EventCreate


def _ensure_area_state_for_update(db: Session, area_id: int) -> AreaState:
    stmt = select(AreaState).where(AreaState.area_id == area_id).with_for_update()
    state = db.execute(stmt).scalar_one_or_none()
    if state is None:
        state = AreaState(area_id=area_id, people_count=0)
        db.add(state)
        db.flush()
        stmt = select(AreaState).where(AreaState.area_id == area_id).with_for_update()
        state = db.execute(stmt).scalar_one()
    return state


def create_event(db: Session, data: EventCreate) -> AreaEvent:
    area = db.get(Area, data.area_id)
    if not area:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Área no encontrada.")

    event_norm = data.event.strip().lower()
    row = AreaEvent(
        timestamp=data.timestamp,
        area_id=data.area_id,
        track_id=data.track_id,
        event=event_norm,
        dwell=float(data.dwell),
    )
    db.add(row)

    state = _ensure_area_state_for_update(db, data.area_id)
    if event_norm == "enter":
        state.people_count += 1
    elif event_norm == "exit":
        state.people_count = max(0, state.people_count - 1)
    state.last_update = datetime.now(timezone.utc).replace(tzinfo=None)

    db.commit()
    db.refresh(row)
    return row
