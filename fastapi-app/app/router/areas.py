from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.data.db import get_db
from app.data.areas import Area as AreaDB
from app.data.area_state import AreaState as AreaStateDB
from app.data.area_events import AreaEvent as AreaEventDB
from app.models.areas import Area as AreaSchema
from typing import List

router = APIRouter(prefix="/api/v1/areas", tags=["Areas"])

@router.post("")
async def create_area(area: AreaSchema, db: Session = Depends(get_db)):
    new_area = AreaDB(
        name=area.name,
        x1=area.x1,
        y1=area.y1,
        x2=area.x2,
        y2=area.y2
    )
    db.add(new_area)
    db.commit()
    db.refresh(new_area)
    
    # Inicializar el estado del área
    new_state = AreaStateDB(area_id=new_area.id, people_count=0)
    db.add(new_state)
    db.commit()
    
    return new_area

@router.get("")
async def get_all_areas(db: Session = Depends(get_db)):
    areas = db.query(AreaDB).order_by(AreaDB.id.asc()).all()
    # Incluir el conteo actual y última actualización
    result = []
    for area in areas:
        state = db.query(AreaStateDB).filter(AreaStateDB.area_id == area.id).first()
        result.append({
            "id": area.id,
            "name": area.name,
            "x1": area.x1,
            "y1": area.y1,
            "x2": area.x2,
            "y2": area.y2,
            "people_count": state.people_count if state else 0,
            "last_update": state.last_update.isoformat() if (state is not None and state.last_update is not None) else None
        })
    return result

@router.get("/{area_id}")
async def get_area(area_id: int, db: Session = Depends(get_db)):
    area = db.query(AreaDB).filter(AreaDB.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")
    return area

@router.patch("/{area_id}")
async def update_area(area_id: int, area_data: dict, db: Session = Depends(get_db)):
    area = db.query(AreaDB).filter(AreaDB.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")
    
    if "name" in area_data:
        area.name = area_data["name"]
    # Podríamos agregar más campos aquí si fuera necesario
    
    db.commit()
    db.refresh(area)
    return area

@router.delete("/{area_id}")
async def delete_area(area_id: int, db: Session = Depends(get_db)):
    area = db.query(AreaDB).filter(AreaDB.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")
    
    # Eliminar estados y eventos asociados primero (o confiar en ON DELETE CASCADE si existe)
    db.query(AreaStateDB).filter(AreaStateDB.area_id == area_id).delete()
    db.query(AreaEventDB).filter(AreaEventDB.area_id == area_id).delete()
    
    db.delete(area)
    db.commit()
    return {"message": f"Area {area_id} and its associated data deleted"}