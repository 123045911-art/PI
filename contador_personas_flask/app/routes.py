from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    render_template,
    request,
    session,
)
import cv2


main_bp = Blueprint("main", __name__)


def get_tracker_service():
    return current_app.extensions.get("tracker_service")


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/health")
def health():
    # Esta ruta se usa para diagnosticar problemas de conectividad Docker/Flask
    return jsonify(
        {
            "status": "ok",
            "api_ready": current_app.extensions.get("api_client") is not None,
            "engine_ready": bool(
                get_tracker_service() and get_tracker_service().initialized
            ),
            "vision": get_tracker_service().health_status()
            if get_tracker_service()
            else None,
        }
    )


@main_bp.route("/video_feed")
def video_feed():
    service = get_tracker_service()
    if not service:
        # En modo diagnóstico, devolvemos un frame de "Modo Diagnóstico"
        import numpy as np

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(
            frame,
            "MODO DIAGNOSTICO: IA Desactivada",
            (50, 240),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
        )
        _, enc = cv2.imencode(".jpg", frame)
        return Response(
            b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + enc.tobytes() + b"\r\n",
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    user = session.get("user") or {}
    client_key = str(user.get("id") or user.get("username") or request.remote_addr or "unknown")
    limiter = current_app.extensions["stream_limiter"]
    if not limiter.acquire(client_key):
        response = jsonify(
            {
                "ok": False,
                "error": "Límite de visualizaciones de cámara alcanzado.",
                "code": "camera_stream_limit_exceeded",
            }
        )
        response.status_code = 429
        response.headers["Retry-After"] = "5"
        return response

    def limited_stream():
        try:
            yield from service.generate_mjpeg_stream()
        finally:
            limiter.release(client_key)

    return Response(
        limited_stream(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@main_bp.route("/stats")
def stats():
    service = get_tracker_service()
    if not service:
        return jsonify({"areas": [], "events_buffered": 0, "diagnostic": True})
    return jsonify(service.get_stats())


@main_bp.route("/add_area", methods=["POST"])
def add_area():
    # Se requiere que el usuario esté autenticado
    if not session.get("user"):
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Acceso denegado. Se requiere iniciar sesión para crear zonas.",
                }
            ),
            401,
        )

    service = get_tracker_service()
    if not service:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Servicio de tracking no disponible en modo diagnóstico.",
                }
            ),
            503,
        )

    payload = request.get_json(silent=True) or request.form.to_dict()

    required_fields = ["name", "x1", "y1", "x2", "y2"]
    missing = [field for field in required_fields if field not in payload]
    if missing:
        return (
            jsonify({"ok": False, "error": f"Campos faltantes: {', '.join(missing)}"}),
            400,
        )

    try:
        area = service.add_area(
            name=str(payload["name"]).strip(),
            x1=int(payload["x1"]),
            y1=int(payload["y1"]),
            x2=int(payload["x2"]),
            y2=int(payload["y2"]),
            is_admin=True,
        )
        return jsonify({"ok": True, "area": area}), 201
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@main_bp.route("/areas/<int:area_id>", methods=["PATCH", "DELETE"])
def mutate_area(area_id: int):
    if not session.get("user"):
        return jsonify({"ok": False, "error": "Acceso denegado. Se requiere iniciar sesión."}), 401
    service = get_tracker_service()
    if not service:
        return jsonify({"ok": False, "error": "Servicio de tracking no disponible."}), 503
    if request.method == "DELETE":
        if not service.delete_area(area_id):
            return jsonify({"ok": False, "error": "Area no encontrada."}), 404
        return jsonify({"ok": True, "areaId": area_id})
    payload = request.get_json(silent=True) or {}
    required = ("name", "x1", "y1", "x2", "y2")
    if any(field not in payload for field in required):
        return jsonify({"ok": False, "error": "Faltan datos del area."}), 400
    try:
        area = service.update_area(
            area_id,
            name=str(payload["name"]),
            x1=int(payload["x1"]), y1=int(payload["y1"]),
            x2=int(payload["x2"]), y2=int(payload["y2"]),
        )
        return jsonify({"ok": True, "area": area})
    except KeyError:
        return jsonify({"ok": False, "error": "Area no encontrada."}), 404
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
