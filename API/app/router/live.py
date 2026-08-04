import os
from typing import Any

import requests
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.data.db import get_db
from app.schemas.alert import AlertCreate, AlertItemOut, AlertListOut, AlertUpdate
from app.security.auth import get_current_user, verify_admin
from app.services import alert_service

router = APIRouter(prefix="/api/v1", tags=["mobile-live"], dependencies=[Depends(get_current_user)])
VISION_SERVICE_URL = os.getenv("VISION_SERVICE_URL", "http://flask_service:5000").rstrip("/")


def _proxy_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        response = requests.get(f"{VISION_SERVICE_URL}{path}", params=params, timeout=(2.0, 12.0))
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail="El motor de visión no está disponible.") from exc
    if not response.ok:
        raise HTTPException(status_code=response.status_code, detail="Respuesta inválida del motor de visión.")
    return response.json()


@router.get("/sites")
def list_sites():
    return _proxy_get("/api/v1/sites")


@router.get("/sites/{site_id}/bootstrap")
def bootstrap(site_id: str):
    return _proxy_get(f"/api/v1/sites/{site_id}/bootstrap")


@router.get("/sites/{site_id}/track-points")
def track_points(site_id: str, request: Request):
    return _proxy_get(f"/api/v1/sites/{site_id}/track-points", dict(request.query_params))


@router.get("/sites/{site_id}/area-state")
def area_state(site_id: str, db: Session = Depends(get_db)):
    payload = _proxy_get(f"/api/v1/sites/{site_id}/area-state")
    counts = {str(item.get("areaId")): int(item.get("peopleCount", 0)) for item in payload.get("items", [])}
    alert_service.evaluate(db, site_id, counts)
    return payload


@router.get("/sites/{site_id}/alerts", response_model=AlertListOut)
def list_alerts(site_id: str, db: Session = Depends(get_db)):
    return {"items": alert_service.list_alerts(db, site_id)}


@router.post("/sites/{site_id}/alerts", response_model=AlertItemOut, status_code=status.HTTP_201_CREATED)
def create_alert(site_id: str, payload: AlertCreate, db: Session = Depends(get_db)):
    return {"item": alert_service.create_alert(db, site_id, payload)}


@router.patch("/sites/{site_id}/alerts/by-area/{area_id}", dependencies=[Depends(verify_admin)])
def rename_alert_area(site_id: str, area_id: str, payload: dict, db: Session = Depends(get_db)):
    area_name = str(payload.get("areaName") or "").strip()
    if not area_name:
        raise HTTPException(status_code=422, detail="areaName es obligatorio.")
    return {"ok": True, "updated": alert_service.rename_for_area(db, site_id, area_id, area_name)}


@router.delete("/sites/{site_id}/alerts/by-area/{area_id}", dependencies=[Depends(verify_admin)])
def delete_alerts_for_area(site_id: str, area_id: str, db: Session = Depends(get_db)):
    return {"ok": True, "deleted": alert_service.delete_for_area(db, site_id, area_id)}


@router.post("/sites/{site_id}/alerts/evaluate", response_model=AlertListOut, dependencies=[Depends(verify_admin)])
def evaluate_alerts(site_id: str, payload: dict, db: Session = Depends(get_db)):
    counts = {str(key): int(value) for key, value in (payload.get("counts") or {}).items()}
    return {"items": alert_service.evaluate(db, site_id, counts)}


@router.patch("/sites/{site_id}/alerts/{alert_id}", response_model=AlertItemOut)
def update_alert(site_id: str, alert_id: str, payload: AlertUpdate, db: Session = Depends(get_db)):
    return {"item": alert_service.update_alert(db, site_id, alert_id, payload)}


@router.delete("/sites/{site_id}/alerts/{alert_id}")
def delete_alert(site_id: str, alert_id: str, db: Session = Depends(get_db)):
    alert_service.delete_alert(db, site_id, alert_id)
    return {"ok": True, "alertId": alert_id}
