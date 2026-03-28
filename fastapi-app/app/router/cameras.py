from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/cameras", tags=["Cameras"])

@router.post("")
async def create_camera():
    return {"message": "Create a new camera"}

@router.get("")
async def get_all_cameras():
    return {"message": "Get all registered cameras"}

@router.get("/{camera_id}")
async def get_camera(camera_id: int):
    return {"message": f"Get details for camera {camera_id}"}

@router.patch("/{camera_id}")
async def update_camera(camera_id: int):
    return {"message": f"Update camera {camera_id}"}

@router.delete("/{camera_id}")
async def delete_camera(camera_id: int):
    return {"message": f"Delete camera {camera_id}"}

@router.get("/{camera_id}/status")
async def get_camera_status(camera_id: int):
    return {"message": f"Status of camera {camera_id}"}

@router.get("/{camera_id}/areas")
async def get_camera_areas(camera_id: int):
    return {"message": f"Get all areas for camera {camera_id}"}

@router.get("/{camera_id}/area-state")
async def get_camera_area_states(camera_id: int):
    return {"message": f"Current state of areas for camera {camera_id}"}