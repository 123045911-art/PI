from __future__ import annotations

import base64
import binascii
from copy import deepcopy
from functools import wraps
from typing import Any

import cv2
import numpy as np
from flask import Blueprint, Response, current_app, jsonify, render_template, request, session

from .scene import generate_fixed_point_matrix, normalize_scene_object


vision_bp = Blueprint("vision_api", __name__)


def _extension(name: str):
    return current_app.extensions[name]


def _payload() -> dict[str, Any]:
    value = request.get_json(silent=True)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("El cuerpo JSON debe ser un objeto")
    return value


def _error(message: str, status: int = 400):
    return jsonify({"ok": False, "error": message}), status


def _admin_required(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        if not session.get("user") and not session.get("is_admin", False):
            return _error("Se requiere iniciar sesión para esta acción.", 401)
        return func(*args, **kwargs)

    return wrapped


def _frame_from_request() -> np.ndarray:
    payload = _payload()
    encoded = payload.get("imageBase64")
    if encoded:
        if isinstance(encoded, str) and encoded.startswith("data:"):
            encoded = encoded.split(",", 1)[-1]
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, TypeError) as exc:
            raise ValueError("imageBase64 no es valido") from exc
        if len(raw) > 12 * 1024 * 1024:
            raise ValueError("La imagen excede el limite de 12 MB")
        frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    else:
        frame = _extension("tracker_service").get_latest_raw_frame()
    if frame is None:
        raise ValueError("No existe un frame de camara disponible")
    return frame


@vision_bp.route("/configuration")
def configuration_view():
    return render_template(
        "configuration.html", vision_config=_extension("vision_config").public_dict()
    )


@vision_bp.get("/api/calibration/status")
def calibration_status():
    tracker = _extension("tracker_service")
    status = _extension("calibration_status_service").get(tracker.get_resolution())
    status["depth"] = _extension("depth_provider").status()
    if status["sensorMode"] in {"rgbd", "stereo"} and not status["depth"]["available"]:
        status["scanReady"] = False
        status["blockers"].append("depth_unavailable")
    status["camera"] = tracker.health_status()
    return jsonify(status)


@vision_bp.post("/api/calibration/intrinsics/capture")
@_admin_required
def capture_intrinsics():
    try:
        return jsonify(_extension("intrinsic_calibration_service").capture(_frame_from_request()))
    except ValueError as exc:
        return _error(str(exc))


@vision_bp.post("/api/calibration/intrinsics/solve")
@_admin_required
def solve_intrinsics():
    try:
        return jsonify(_extension("intrinsic_calibration_service").solve())
    except (ValueError, cv2.error) as exc:
        return _error(str(exc))


@vision_bp.post("/api/calibration/world/solve")
@_admin_required
def solve_world():
    try:
        return jsonify(_extension("world_calibration_service").solve(_payload()))
    except (ValueError, cv2.error, np.linalg.LinAlgError) as exc:
        return _error(str(exc))


@vision_bp.post("/api/calibration/validate")
@_admin_required
def validate_calibration():
    try:
        return jsonify(_extension("world_calibration_service").validate(_payload()))
    except (ValueError, KeyError) as exc:
        return _error(str(exc))


@vision_bp.post("/api/scene/scan/start")
@_admin_required
def start_scene_scan():
    try:
        return jsonify(_extension("scene_scanner").start()), 202
    except ValueError as exc:
        return _error(str(exc), 409)


@vision_bp.get("/api/scene/scan/status")
def scene_scan_status():
    return jsonify(_extension("scene_scanner").status())


@vision_bp.post("/api/scene/scan/stop")
@_admin_required
def stop_scene_scan():
    return jsonify(_extension("scene_scanner").stop())


def _scene_with_defaults() -> dict[str, Any]:
    calibration = _extension("calibration_repository").load_world() or {}
    return _extension("scene_repository").load_or_empty(
        int(calibration.get("version", 0))
    )


def _save_scene(scene: dict[str, Any]) -> dict[str, Any]:
    config = _extension("vision_config")
    calibration = _extension("calibration_repository").load_world()
    if not calibration:
        raise ValueError("No se puede guardar una escena sin calibracion del mundo")
    result = deepcopy(scene)
    result["objects"] = [
        normalize_scene_object(item, config) for item in result.get("objects", [])
    ]
    result["calibrationVersion"] = int(calibration["version"])
    if not result.get("fieldOfViewPolygon"):
        intrinsics = _extension("calibration_repository").load_intrinsics() or {}
        result["fieldOfViewPolygon"] = _extension("coordinate_transformer").field_of_view_polygon(
            int(intrinsics.get("imageWidth", 0)), int(intrinsics.get("imageHeight", 0))
        )
    resolution = float(
        result.pop("gridResolutionMeters", config.grid_resolution_meters)
    )
    result["fixedPointMatrixResolutionMeters"] = resolution
    result["fixedPointMatrix"] = generate_fixed_point_matrix(result, resolution)
    return _extension("scene_repository").save(result)


@vision_bp.get("/api/scene")
def get_scene():
    return jsonify(_scene_with_defaults())


@vision_bp.put("/api/scene")
@_admin_required
def put_scene():
    try:
        payload = _payload()
        if payload.get("acceptScanProposals"):
            proposals = _extension("scene_scanner").status().get("proposals", [])
            payload["objects"] = payload.get("objects", []) + proposals
        return jsonify(_save_scene(payload))
    except ValueError as exc:
        return _error(str(exc))


@vision_bp.post("/api/scene/objects")
@_admin_required
def add_scene_object():
    try:
        scene = _scene_with_defaults()
        scene["objects"].append(normalize_scene_object(_payload(), _extension("vision_config")))
        return jsonify(_save_scene(scene)), 201
    except ValueError as exc:
        return _error(str(exc))


@vision_bp.patch("/api/scene/objects/<object_id>")
@_admin_required
def patch_scene_object(object_id: str):
    try:
        scene = _scene_with_defaults()
        patch = _payload()
        for index, item in enumerate(scene.get("objects", [])):
            if item.get("id") == object_id:
                scene["objects"][index] = normalize_scene_object(
                    {**item, **patch, "id": object_id}, _extension("vision_config")
                )
                return jsonify(_save_scene(scene))
        return _error("Objeto no encontrado.", 404)
    except ValueError as exc:
        return _error(str(exc))


@vision_bp.delete("/api/scene/objects/<object_id>")
@_admin_required
def delete_scene_object(object_id: str):
    scene = _scene_with_defaults()
    before = len(scene.get("objects", []))
    scene["objects"] = [item for item in scene.get("objects", []) if item.get("id") != object_id]
    if len(scene["objects"]) == before:
        return _error("Objeto no encontrado.", 404)
    try:
        return jsonify(_save_scene(scene))
    except ValueError as exc:
        return _error(str(exc))


@vision_bp.get("/api/live/tracks")
def live_tracks():
    return jsonify(_extension("tracker_service").get_live_tracks())


@vision_bp.get("/api/live/frame")
def live_frame():
    return Response(_extension("tracker_service").get_latest_jpeg(), mimetype="image/jpeg")


@vision_bp.get("/api/stream")
def live_stream():
    return Response(
        _extension("tracker_service").generate_mjpeg_stream(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@vision_bp.get("/api/coordinates/image-to-ground")
def image_to_ground():
    try:
        u = float(request.args["u"])
        v = float(request.args["v"])
        point = _extension("coordinate_transformer").image_ground_point(u, v)
        return jsonify(
            {
                "imagePoint": {"u": u, "v": v, "coordinateSystem": "image_pixels"},
                "worldPoint": point.as_dict(),
            }
        )
    except (KeyError, ValueError) as exc:
        return _error(str(exc))
