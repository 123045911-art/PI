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
            "status": "diagnostic_mode",
            "api_ready": current_app.extensions.get("api_client") is not None,
            "engine_ready": False,  # Deshabilitado para diagnósticos
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

    return Response(
        service.generate_mjpeg_stream(),
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
    # Solo el administrador puede crear zonas
    if not session.get("is_admin", False):
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Acceso denegado. Solo administradores pueden crear zonas.",
                }
            ),
            403,
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
            is_admin=True,  # El check anterior ya validó session.get("is_admin")
        )
        return jsonify({"ok": True, "area": area}), 201
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
