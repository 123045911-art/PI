from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.data.db import get_db
from app.schemas.area import AreaCreate, AreaOut, AreaUpdate
from app.services import area_service
from app.security.auth import verify_admin

router = APIRouter(tags=["areas"])


@router.post("/areas", response_model=AreaOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin)])
def create_area(payload: AreaCreate, db: Session = Depends(get_db)):
    return area_service.create_area(db, payload)


@router.get("/areas", response_model=list[AreaOut])
def list_areas(db: Session = Depends(get_db)):
    return area_service.list_areas(db)


@router.get("/areas/{area_id}", response_model=AreaOut)
def get_area(area_id: int, db: Session = Depends(get_db)):
    return area_service.get_area(db, area_id)


@router.put("/areas/{area_id}", response_model=AreaOut, dependencies=[Depends(verify_admin)])
def update_area(area_id: int, payload: AreaUpdate, db: Session = Depends(get_db)):
    return area_service.update_area(db, area_id, payload)


@router.delete("/areas/{area_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(verify_admin)])
def delete_area(area_id: int, db: Session = Depends(get_db)):
    area_service.delete_area(db, area_id)
