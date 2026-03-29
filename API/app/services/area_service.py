from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.area import Area
from app.models.area_state import AreaState
from app.schemas.area import AreaCreate, AreaUpdate


def create_area(db: Session, data: AreaCreate) -> Area:
    area = Area(
        name=data.name.strip(),
        x1=data.x1,
        y1=data.y1,
        x2=data.x2,
        y2=data.y2,
    )
    db.add(area)
    db.flush()
    db.add(AreaState(area_id=area.id, people_count=0))
    db.commit()
    db.refresh(area)
    return area


def list_areas(db: Session) -> list[Area]:
    return db.query(Area).order_by(Area.id).all()


def get_area(db: Session, area_id: int) -> Area:
    area = db.get(Area, area_id)
    if not area:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Área no encontrada.")
    return area


def update_area(db: Session, area_id: int, data: AreaUpdate) -> Area:
    area = get_area(db, area_id)
    payload = data.model_dump(exclude_unset=True)
    for key, value in payload.items():
        if key == "name" and isinstance(value, str):
            value = value.strip()
        setattr(area, key, value)
    db.commit()
    db.refresh(area)
    return area


def delete_area(db: Session, area_id: int) -> None:
    area = get_area(db, area_id)
    db.delete(area)
    db.commit()
