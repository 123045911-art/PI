from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from threading import RLock
from typing import Any
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request


demo_api_bp = Blueprint("demo_api", __name__)

CORRIDOR_SITE_ID = "pasillo-real"
SIMULATED_SITE_ID = "sitio-simulado"

CORRIDOR_AREAS = [
    {
        "areaId": "zona-cercana",
        "name": "Zona cercana",
        "kind": "access",
        "polygon": [[0.05, 0.0], [1.65, 0.0], [1.65, 0.9], [0.05, 0.9]],
        "bounds": {"x": 0.05, "y": 0.0, "width": 1.6, "height": 0.9},
        "imageRect": [245, 585, 735, 719],
    },
    {
        "areaId": "zona-media",
        "name": "Zona media",
        "kind": "transit",
        "polygon": [[0.18, 0.9], [1.62, 0.9], [1.62, 2.25], [0.18, 2.25]],
        "bounds": {"x": 0.18, "y": 0.9, "width": 1.44, "height": 1.35},
        "imageRect": [285, 505, 575, 584],
    },
    {
        "areaId": "zona-lejana",
        "name": "Zona lejana",
        "kind": "interaction",
        "polygon": [[0.35, 2.25], [1.62, 2.25], [1.62, 4.5], [0.35, 4.5]],
        "bounds": {"x": 0.35, "y": 2.25, "width": 1.27, "height": 2.25},
        "imageRect": [325, 415, 485, 504],
    },
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _area_for_point(x: float, y: float) -> str | None:
    for area in _runtime_corridor_areas():
        bounds = area["bounds"]
        if (
            bounds["x"] <= x <= bounds["x"] + bounds["width"]
            and bounds["y"] <= y <= bounds["y"] + bounds["height"]
        ):
            return str(area["areaId"])
    return None


def _public_area(area: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in area.items() if key != "imageRect"}


def _runtime_corridor_areas() -> list[dict[str, Any]]:
    tracker = current_app.extensions["tracker_service"]
    fixed = {area["areaId"]: area for area in CORRIDOR_AREAS}
    result: list[dict[str, Any]] = []
    with tracker.lock:
        runtime_areas = [dict(area) for area in tracker.areas.values()]
    if not runtime_areas:
        return [dict(area) for area in CORRIDOR_AREAS]
    for area in runtime_areas:
        external_id = str(area.get("external_id") or f"area-local-{area['id']}")
        if external_id in fixed:
            result.append(dict(fixed[external_id]))
            continue
        x1, y1, x2, y2 = (int(area[key]) for key in ("x1", "y1", "x2", "y2"))
        world_x1 = max(0.0, min(1.75, x1 / 960.0 * 1.75))
        world_x2 = max(0.0, min(1.75, x2 / 960.0 * 1.75))
        world_y1 = max(0.0, min(4.5, (720 - y2) / 305.0 * 4.5))
        world_y2 = max(0.0, min(4.5, (720 - y1) / 305.0 * 4.5))
        result.append(
            {
                "areaId": external_id,
                "name": str(area["name"]),
                "kind": "transit",
                "polygon": [
                    [world_x1, world_y1], [world_x2, world_y1],
                    [world_x2, world_y2], [world_x1, world_y2],
                ],
                "bounds": {
                    "x": world_x1, "y": world_y1,
                    "width": max(0.01, world_x2 - world_x1),
                    "height": max(0.01, world_y2 - world_y1),
                },
                "imageRect": [x1, y1, x2, y2],
            }
        )
    return result


class DemoLiveStore:
    def __init__(self, max_points: int = 12000) -> None:
        self.lock = RLock()
        self.session_id = str(uuid4())
        self.points: deque[dict[str, Any]] = deque(maxlen=max_points)
        self.seen: set[tuple[int, str]] = set()

    def capture(self, snapshot: dict[str, Any]) -> None:
        frame_id = int(snapshot.get("frameId") or 0)
        captured_at = snapshot.get("capturedAt") or _utc_now()
        with self.lock:
            for track in snapshot.get("tracks", []):
                if not track.get("positionValid"):
                    continue
                tracker_id = str(track.get("trackerId"))
                identity = (frame_id, tracker_id)
                if identity in self.seen:
                    continue
                self.seen.add(identity)
                world = track.get("worldPoint") or {}
                x = float(track.get("x", world.get("x", 0.0)))
                y = float(track.get("y", world.get("y", 0.0)))
                z = float(track.get("z", world.get("z", 0.0)))
                image = track.get("imagePoint") or {}
                self.points.append(
                    {
                        "cameraId": snapshot.get("cameraId", "dell-wb7022"),
                        "sessionId": self.session_id,
                        "frameId": frame_id,
                        "trackerId": tracker_id,
                        "capturedAt": captured_at,
                        "imagePoint": {"u": image.get("u"), "v": image.get("v")},
                        "x": x,
                        "y": y,
                        "z": z,
                        "areaId": _area_for_point(x, y),
                        "confidence": float(track.get("confidence", 0.0)),
                    }
                )
            if len(self.seen) > 24000:
                self.seen = {(int(item["frameId"]), str(item["trackerId"])) for item in self.points}

    def list_points(self, limit: int, after_frame_id: int | None = None) -> list[dict[str, Any]]:
        with self.lock:
            points = list(self.points)
            if after_frame_id is not None:
                points = [item for item in points if int(item["frameId"]) > after_frame_id]
                return points[:limit]
            return points[-limit:]


def seed_corridor_areas(tracker: Any) -> None:
    for area in CORRIDOR_AREAS:
        x1, y1, x2, y2 = area["imageRect"]
        tracker.add_local_area(
            area["name"], x1, y1, x2, y2, external_id=area["areaId"]
        )


def _corridor_scene() -> dict[str, Any]:
    repository = current_app.extensions["scene_repository"]
    source = repository.load_or_empty(1)
    objects = []
    for item in source.get("objects", []):
        converted = dict(item)
        converted["objectId"] = converted.pop("id", "obj-fixed")
        objects.append(converted)
    return {
        "cameraId": "dell-wb7022",
        "coordinateSystem": {
            "name": "world_ground",
            "unit": "meter",
            "origin": "tile_A_approximate",
            "xAxis": "right",
            "yAxis": "forward",
            "zAxis": "up",
        },
        "calibrationVersion": int(source.get("calibrationVersion", 1)),
        "fieldOfViewPolygon": [[0.0, 0.0], [1.75, 0.0], [1.75, 4.5], [0.0, 4.5]],
        "operationalAreas": [_public_area(area) for area in _runtime_corridor_areas()],
        "objects": objects,
        "fixedPointMatrixResolutionMeters": source.get("fixedPointMatrixResolutionMeters", 0.1),
        "createdAt": source.get("createdAt") or _utc_now(),
        "version": int(source.get("version", 1)),
    }


@demo_api_bp.get("/api/v1/sites")
def list_sites():
    return jsonify(
        {
            "items": [
                {"siteId": CORRIDOR_SITE_ID, "name": "Mi pasillo", "mode": "live"},
                {"siteId": SIMULATED_SITE_ID, "name": "Sitio simulado", "mode": "simulated"},
            ]
        }
    )


@demo_api_bp.get("/api/v1/sites/<site_id>/bootstrap")
def site_bootstrap(site_id: str):
    if site_id != CORRIDOR_SITE_ID:
        return jsonify({"ok": False, "error": "El sitio simulado se conserva dentro de la app."}), 404
    scene = _corridor_scene()
    return jsonify(
        {
            "siteId": CORRIDOR_SITE_ID,
            "name": "Mi pasillo",
            "timezone": "America/Mexico_City",
            "cameras": [
                {
                    "siteId": CORRIDOR_SITE_ID,
                    "cameraId": "dell-wb7022",
                    "name": "Dell Webcam WB7022",
                    "sensorMode": "monocular",
                    "active": True,
                }
            ],
            "areas": scene["operationalAreas"],
            "scenes": [scene],
        }
    )


@demo_api_bp.get("/api/v1/sites/<site_id>/track-points")
def site_track_points(site_id: str):
    if site_id != CORRIDOR_SITE_ID:
        return jsonify({"items": [], "nextCursor": None})
    limit = max(1, min(int(request.args.get("limit", 4000)), 12000))
    cursor = request.args.get("cursor")
    after_frame_id = int(cursor) if cursor and cursor.isdigit() else None
    tracker = current_app.extensions["tracker_service"]
    store: DemoLiveStore = current_app.extensions["demo_live_store"]
    store.capture(tracker.get_live_tracks())
    items = store.list_points(limit, after_frame_id)
    next_cursor = str(items[-1]["frameId"]) if items else cursor
    return jsonify({"items": items, "nextCursor": next_cursor})


@demo_api_bp.get("/api/v1/sites/<site_id>/area-state")
def site_area_state(site_id: str):
    if site_id != CORRIDOR_SITE_ID:
        return jsonify({"items": []})
    tracker = current_app.extensions["tracker_service"]
    store: DemoLiveStore = current_app.extensions["demo_live_store"]
    snapshot = tracker.get_live_tracks()
    store.capture(snapshot)
    counts = {area["areaId"]: 0 for area in _runtime_corridor_areas()}
    # El rectangulo que ve el operador en Flask es la fuente autoritativa del
    # conteo. La posicion mundial puede ser invalida si la calibracion es
    # aproximada; eso no debe impedir que se active una alerta.
    for area in tracker.get_stats().get("areas", []):
        area_id = str(area.get("external_id") or f"area-local-{area['id']}")
        if area_id in counts:
            counts[area_id] = int(area.get("current_count", 0))
    observed_at = snapshot.get("capturedAt") or _utc_now()
    current_app.extensions["alert_store"].evaluate(CORRIDOR_SITE_ID, counts)
    return jsonify(
        {
            "items": [
                {
                    "cameraId": "dell-wb7022",
                    "areaId": area_id,
                    "peopleCount": count,
                    "observedAt": observed_at,
                }
                for area_id, count in counts.items()
            ]
        }
    )


@demo_api_bp.route("/api/v1/sites/<site_id>/alerts", methods=["GET", "POST", "OPTIONS"])
def site_alerts(site_id: str):
    if request.method == "OPTIONS":
        return "", 204
    store = current_app.extensions["alert_store"]
    if request.method == "GET":
        return jsonify({"items": store.list(site_id)})
    try:
        return jsonify({"item": store.create(site_id, request.get_json(silent=True) or {})}), 201
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@demo_api_bp.route(
    "/api/v1/sites/<site_id>/alerts/<alert_id>",
    methods=["PATCH", "DELETE", "OPTIONS"],
)
def site_alert(site_id: str, alert_id: str):
    if request.method == "OPTIONS":
        return "", 204
    store = current_app.extensions["alert_store"]
    if request.method == "DELETE":
        if not store.delete(site_id, alert_id):
            return jsonify({"ok": False, "error": "Alerta no encontrada."}), 404
        return jsonify({"ok": True, "alertId": alert_id})
    item = store.update(site_id, alert_id, request.get_json(silent=True) or {})
    if not item:
        return jsonify({"ok": False, "error": "Alerta no encontrada."}), 404
    return jsonify({"item": item})
