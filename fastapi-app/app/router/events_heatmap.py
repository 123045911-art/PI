from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["Events & Heatmap"])

# --- Eventos ---
@router.post("/events")
async def register_event():
    return {"message": "Register single event (entry/exit)"}

@router.post("/events/bulk")
async def register_events_bulk():
    return {"message": "Register multiple events"}

@router.get("/events")
async def get_events():
    return {"message": "Get events with filters"}

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