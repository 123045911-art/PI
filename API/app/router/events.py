from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.data.db import get_db
from app.schemas.event import EventCreate, EventOut
from app.services import event_service

router = APIRouter(tags=["events"])


@router.post(
    "/events",
    response_model=EventOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar evento de área",
)
def ingest_event(payload: EventCreate, db: Session = Depends(get_db)):
    """Recibe eventos desde Flask (entrada/salida, dwell, etc.). Persiste en PostgreSQL."""
    return event_service.create_event(db, payload)
