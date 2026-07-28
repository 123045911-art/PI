from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.data.db import get_db
from app.schemas.state import AreaStateOut, StateListOut
from app.security.auth import get_current_user
from app.services import state_service

router = APIRouter(prefix="/state", tags=["state"])


@router.get("", response_model=StateListOut, dependencies=[Depends(get_current_user)])
def get_state(db: Session = Depends(get_db)):
    return state_service.get_full_state(db)


@router.get("/{area_id}", response_model=AreaStateOut, dependencies=[Depends(get_current_user)])
def get_state_for_area(area_id: int, db: Session = Depends(get_db)):
    return state_service.get_state_by_area(db, area_id)
