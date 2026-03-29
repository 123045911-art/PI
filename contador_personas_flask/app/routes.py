from flask import Blueprint, Response, current_app, jsonify, render_template, request, session


main_bp = Blueprint("main", __name__)


def get_tracker_service():
    return current_app.extensions["tracker_service"]


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/video_feed")
def video_feed():
    service = get_tracker_service()
    return Response(
        service.generate_mjpeg_stream(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@main_bp.route("/stats")
def stats():
    service = get_tracker_service()
    return jsonify(service.get_stats())


@main_bp.route("/add_area", methods=["POST"])
def add_area():
    # Solo el administrador puede crear zonas
    if not session.get("is_admin", False):
        return jsonify({"ok": False, "error": "Acceso denegado. Solo administradores pueden crear zonas."}), 403

    service = get_tracker_service()
    payload = request.get_json(silent=True) or request.form.to_dict()

    required_fields = ["name", "x1", "y1", "x2", "y2"]
    missing = [field for field in required_fields if field not in payload]
    if missing:
        return jsonify({"ok": False, "error": f"Campos faltantes: {', '.join(missing)}"}), 400

    try:
        area = service.add_area(
            name=str(payload["name"]).strip(),
            x1=int(payload["x1"]),
            y1=int(payload["y1"]),
            x2=int(payload["x2"]),
            y2=int(payload["y2"]),
            is_admin=True # El check anterior ya validó session.get("is_admin")
        )
        return jsonify({"ok": True, "area": area}), 201
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
