from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["Areas"])

@router.post("/areas")
async def create_area():
    return {"message": "Create a new detection area"}

@router.get("/areas")
async def get_all_areas():
    return {"message": "Get all areas"}

@router.get("/areas/{area_id}")
async def get_area(area_id: int):
    return {"message": f"Get details for area {area_id}"}

@router.patch("/areas/{area_id}")
async def update_area(area_id: int):
    return {"message": f"Update area {area_id}"}

@router.delete("/areas/{area_id}")
async def delete_area(area_id: int):
    return {"message": f"Delete area {area_id}"}

@router.put("/area-state/{area_id}")
async def update_area_state(area_id: int):
    return {"message": f"Update person count for area {area_id}"}

@router.post("/area-state/sync")
async def sync_area_states():
    return {"message": "Sync current state of all areas for a camera"}

@router.get("/area-state")
async def get_all_area_states():
    return {"message": "Get current state of all areas"}