from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.data.db import get_db
from app.data.area_events import AreaEvent as AreaEventDB
from app.data.areas import Area as AreaDB
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/api/v1", tags=["Events & Heatmap"])

# --- Eventos ---
@router.post("/events")
async def register_event():
    return {"message": "Register single event (entry/exit)"}

@router.post("/events/bulk")
async def register_events_bulk():
    return {"message": "Register multiple events"}

@router.get("/events")
async def get_events(
    limit: int = 50, 
    offset: int = 0, 
    db: Session = Depends(get_db)
):
    query = db.query(AreaEventDB, AreaDB.name).join(
        AreaDB, AreaDB.id == AreaEventDB.area_id
    ).order_by(AreaEventDB.timestamp.desc())
    
    total = query.count()
    events_raw = query.offset(offset).limit(limit).all()
    
    events = []
    for event, area_name in events_raw:
        events.append({
            "id": event.id,
            "timestamp": event.timestamp.isoformat(),
            "area_id": event.area_id,
            "area_name": area_name,
            "track_id": event.track_id,
            "event": event.event.upper(),
            "dwell": event.dwell
        })
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": events
    }

@router.get("/events/{event_id}")
async def get_event_details(event_id: int):
    return {"message": f"Get event {event_id}"}

# --- Heatmap ---
@router.post("/heatmap-points")
async def register_heatmap_point():
    return {"message": "Register a single heatmap position point"}

@router.post("/heatmap-points/bulk")
async def register_heatmap_points_bulk():
    return {"message": "Register multiple heatmap points"}

@router.get("/heatmap")
async def get_heatmap_data():
    return {"message": "Get heatmap data with filters"}