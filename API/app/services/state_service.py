from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.area import Area
from app.models.area_state import AreaState
from app.schemas.state import AreaStateOut, StateListOut


def get_full_state(db: Session) -> StateListOut:
    rows = db.query(AreaState).order_by(AreaState.area_id).all()
    total = db.query(func.coalesce(func.sum(AreaState.people_count), 0)).scalar()
    total_people = int(total or 0)
    return StateListOut(
        items=[AreaStateOut.model_validate(r) for r in rows],
        total_people=total_people,
    )


def get_state_by_area(db: Session, area_id: int) -> AreaStateOut:
    if not db.get(Area, area_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Área no encontrada."
        )
    row = db.get(AreaState, area_id)
    if not row:
        return AreaStateOut(area_id=area_id, people_count=0, last_update=None)
    return AreaStateOut.model_validate(row)
