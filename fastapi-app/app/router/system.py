from fastapi import APIRouter

router = APIRouter(tags=["System"])

@router.get("/health")
async def health_check():
    return {"status": "ok", "message": "API is up and running"}

@router.get("/api/v1/system/status")
async def system_status():
    return {"api": "active", "database": "connected"}