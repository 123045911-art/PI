from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date
from app.data.db import get_db
from app.data.areas import Area
from app.data.area_state import AreaState
from app.data.area_events import AreaEvent

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])

@router.get("/summary")
async def get_dashboard_summary(db: Session = Depends(get_db)):
    # 1. Total de personas actualmente (suma de people_count en area_state)
    total_personas_result = db.query(func.sum(AreaState.people_count)).scalar()
    total_personas = int(total_personas_result) if total_personas_result is not None else 0
    
    # 2. Áreas activas (aquellas con people_count > 0)
    areas_activas = db.query(AreaState).filter(AreaState.people_count > 0).count()
    
    # 3. Entradas y Salidas de hoy
    today = date.today()
    entradas_hoy = db.query(AreaEvent).filter(
        func.date(AreaEvent.timestamp) == today,
        AreaEvent.event.ilike('enter')
    ).count()
    
    salidas_hoy = db.query(AreaEvent).filter(
        func.date(AreaEvent.timestamp) == today,
        AreaEvent.event.ilike('exit')
    ).count()
    
    # 4. Conteo por área para la gráfica
    # Unimos Area con AreaState para obtener el nombre y el conteo actual
    conteo_por_area_raw = db.query(Area.name, AreaState.people_count).join(
        AreaState, Area.id == AreaState.area_id
    ).all()
    
    conteo_por_area = [
        {"name": row.name, "count": row.people_count} 
        for row in conteo_por_area_raw
    ]
    
    # 5. Últimos 10 eventos
    eventos_recientes_raw = db.query(
        AreaEvent.timestamp, Area.name, AreaEvent.event, AreaEvent.track_id
    ).join(Area, Area.id == AreaEvent.area_id).order_by(
        AreaEvent.timestamp.desc()
    ).limit(10).all()
    
    eventos_recientes = [
        {
            "hora": row.timestamp.strftime("%H:%M:%S"),
            "area_name": row.name,
            "event": row.event.upper(),
            "track_id": row.track_id
        }
        for row in eventos_recientes_raw
    ]
    
    return {
        "total_personas": total_personas,
        "areas_activas": areas_activas,
        "entradas_hoy": entradas_hoy,
        "salidas_hoy": salidas_hoy,
        "conteo_por_area": conteo_por_area,
        "eventos_recientes": eventos_recientes
    }

@router.get("/by-area")
async def get_metrics_by_area():
    return {"message": "Metrics grouped by area"}

@router.get("/by-camera")
async def get_metrics_by_camera():
    return {"message": "Metrics grouped by camera"}

@router.get("/timeseries")
async def get_timeseries_data():
    return {"message": "Historical data as timeseries"}

@router.get("/dwell")
async def get_dwell_metrics():
    return {"message": "Dwell time metrics by area"}