from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])

@router.get("/summary")
async def get_dashboard_summary():
    return {"message": "System summary (people, entries, exits)"}

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