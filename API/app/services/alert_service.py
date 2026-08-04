from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.schemas.alert import AlertCreate, AlertUpdate


def list_alerts(db: Session, site_id: str) -> list[Alert]:
    return db.query(Alert).filter(Alert.site_id == site_id).order_by(Alert.created_at.desc()).all()


def create_alert(db: Session, site_id: str, data: AlertCreate) -> Alert:
    if data.type in {"crowding", "low_flow"} and data.threshold_people is None:
        raise HTTPException(status_code=422, detail="thresholdPeople es obligatorio para esta alerta.")
    generated = (
        f"Avisar cuando haya {data.threshold_people} personas o más."
        if data.type == "crowding"
        else f"Avisar cuando haya {data.threshold_people} personas o menos."
        if data.type == "low_flow"
        else "Condición operativa registrada."
    )
    item = Alert(
        id=data.id or f"alert-{uuid4().hex[:12]}", site_id=site_id,
        area_id=data.area_id, area_name=data.area_name, type=data.type,
        reason=data.reason.strip() or generated, status=data.status,
        threshold_people=data.threshold_people, schedule_mode=data.schedule_mode,
        schedule_day=data.schedule_day, schedule_date=data.schedule_date,
        people_count_snapshot=data.people_count_snapshot, created_by=data.created_by,
        created_at=data.created_at or datetime.utcnow(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_alert(db: Session, site_id: str, alert_id: str) -> Alert:
    item = db.get(Alert, alert_id)
    if not item or item.site_id != site_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alerta no encontrada.")
    return item


def update_alert(db: Session, site_id: str, alert_id: str, data: AlertUpdate) -> Alert:
    item = get_alert(db, site_id, alert_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete_alert(db: Session, site_id: str, alert_id: str) -> None:
    item = get_alert(db, site_id, alert_id)
    db.delete(item)
    db.commit()


def delete_for_area(db: Session, site_id: str, area_id: str) -> int:
    count = db.query(Alert).filter(Alert.site_id == site_id, Alert.area_id == area_id).delete(synchronize_session=False)
    db.commit()
    return count


def rename_for_area(db: Session, site_id: str, area_id: str, area_name: str) -> int:
    count = db.query(Alert).filter(Alert.site_id == site_id, Alert.area_id == area_id).update(
        {Alert.area_name: area_name}, synchronize_session=False
    )
    db.commit()
    return count


def evaluate(db: Session, site_id: str, counts: dict[str, int], now: datetime | None = None) -> list[Alert]:
    now = now or datetime.now()
    items = list_alerts(db, site_id)
    changed = False
    for item in items:
        mode = item.schedule_mode or "all_days"
        applies = mode == "all_days"
        if mode == "weekly":
            applies = item.schedule_day == now.weekday()
        elif mode == "date":
            applies = item.schedule_date == now.date().isoformat()
        count = int(counts.get(item.area_id, 0))
        crowding_threshold = 1 if item.threshold_people is None else int(item.threshold_people)
        low_flow_threshold = 0 if item.threshold_people is None else int(item.threshold_people)
        met = count >= crowding_threshold if item.type == "crowding" else (
            count <= low_flow_threshold if item.type == "low_flow" else False
        )
        next_status = "triggered" if applies and met else "watching"
        if item.status != next_status or item.people_count_snapshot != count:
            item.status = next_status
            item.people_count_snapshot = count
            changed = True
    if changed:
        db.commit()
    return items
