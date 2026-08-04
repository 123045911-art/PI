import logging
import os

from flask import Flask, jsonify, session, redirect, url_for, request, current_app, g

from app.core.tracker_service import TrackerService
from app.core.api_client import VisioFlowApiClient
from app.core.request_limits import SlidingWindowRateLimiter, StreamLimiter
from app.core.local_users import LocalUserStore
from app.core.alert_store import AlertStore
from app.routes import main_bp
from app.auth_routes import auth_bp
from app.user_routes import user_bp
from app.demo_api import DemoLiveStore, demo_api_bp, seed_corridor_areas
from app.vision.api import vision_bp
from app.vision.calibration import (
    CalibrationStatusService,
    IntrinsicCalibrationService,
    WorldCalibrationService,
)
from app.vision.config import VisionConfig
from app.vision.depth import create_depth_provider
from app.vision.geometry import CoordinateTransformer
from app.vision.repositories import CalibrationRepository, SceneRepository
from app.vision.scene import SceneScanner, create_segmentation_provider


def create_app(
    *,
    start_background: bool | None = None,
    vision_config: VisionConfig | None = None,
) -> Flask:
    if not logging.root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s %(name)s %(message)s",
        )

    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    # SEGURIDAD: La secret_key DEBE venir de la variable de entorno FLASK_SECRET_KEY.
    # Si no está definida, la aplicación NO arranca — esto es intencional para
    # evitar correr con una clave insegura hardcodeada.
    secret_key = os.getenv("FLASK_SECRET_KEY")
    if not secret_key:
        raise RuntimeError(
            "La variable de entorno FLASK_SECRET_KEY no está definida.\n"
            "Genera una clave segura con: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    app.secret_key = secret_key

    # Configuración de cookies de sesión seguras
    app.config["SESSION_COOKIE_HTTPONLY"] = True    # No accesible por JS
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"   # Protección CSRF
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("APP_ENV", "production") == "production"

    # Servicios de vision y persistencia versionada.
    vision_config = vision_config or VisionConfig.from_env()
    calibration_repository = CalibrationRepository(vision_config)
    scene_repository = SceneRepository(vision_config)
    coordinate_transformer = CoordinateTransformer(
        vision_config, calibration_repository
    )
    depth_provider = create_depth_provider(vision_config)
    intrinsic_service = IntrinsicCalibrationService(
        vision_config, calibration_repository
    )
    world_service = WorldCalibrationService(
        vision_config, calibration_repository, coordinate_transformer
    )
    calibration_status_service = CalibrationStatusService(
        vision_config, calibration_repository, intrinsic_service
    )

    app.extensions["vision_config"] = vision_config
    app.extensions["local_user_store"] = LocalUserStore(vision_config.data_root)
    app.extensions["alert_store"] = AlertStore(vision_config.data_root)
    app.extensions["calibration_repository"] = calibration_repository
    app.extensions["scene_repository"] = scene_repository
    app.extensions["coordinate_transformer"] = coordinate_transformer
    app.extensions["depth_provider"] = depth_provider
    app.extensions["intrinsic_calibration_service"] = intrinsic_service
    app.extensions["world_calibration_service"] = world_service
    app.extensions["calibration_status_service"] = calibration_status_service

    # Integracion existente con FastAPI.
    api_client = VisioFlowApiClient()
    app.extensions["api_client"] = api_client

    service_user = os.getenv("API_SERVICE_USERNAME")
    service_pass = os.getenv("API_SERVICE_PASSWORD")
    if service_user and service_pass:
        service_token = api_client.authenticate(service_user, service_pass)
        if service_token:
            api_client.set_service_token(service_token)
            logging.getLogger("visioflow.api").info(
                "Token de servicio configurado para el cliente API."
            )
        else:
            logging.getLogger("visioflow.api").warning(
                "No se pudo autenticar la cuenta de servicio API (%s).",
                service_user,
            )
    else:
        logging.getLogger("visioflow.api").warning(
            "API_SERVICE_USERNAME/API_SERVICE_PASSWORD no definidos; "
            "el envío de eventos en background requerirá login de usuario."
        )

    if start_background is None:
        start_background = os.getenv("VISIOFLOW_START_BACKGROUND", "1") == "1"
    tracker_service = TrackerService(
        api_client=api_client,
        coordinate_transformer=coordinate_transformer,
        depth_provider=depth_provider,
        scene_repository=scene_repository,
        camera_id=vision_config.camera_id,
        start_background=start_background,
    )
    app.extensions["tracker_service"] = tracker_service
    app.extensions["demo_live_store"] = DemoLiveStore()
    app.extensions["api_rate_limiter"] = SlidingWindowRateLimiter(
        per_client=int(os.getenv("API_RATE_LIMIT_REQUESTS", "80")),
        global_limit=int(os.getenv("API_GLOBAL_RATE_LIMIT_REQUESTS", "1200")),
        window_seconds=float(os.getenv("API_RATE_LIMIT_WINDOW_SECONDS", "10")),
    )
    app.extensions["stream_limiter"] = StreamLimiter(
        global_limit=int(os.getenv("MAX_MJPEG_STREAMS", "4")),
        per_client=int(os.getenv("MAX_MJPEG_STREAMS_PER_USER", "1")),
    )
    if vision_config.camera_id == "dell-wb7022":
        seed_corridor_areas(tracker_service)

    segmentation_provider = create_segmentation_provider(vision_config)
    app.extensions["segmentation_provider"] = segmentation_provider
    app.extensions["scene_scanner"] = SceneScanner(
        vision_config,
        calibration_repository,
        scene_repository,
        coordinate_transformer,
        depth_provider,
        segmentation_provider,
        tracker_service.get_latest_raw_frame,
    )

    # Blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(vision_bp)
    app.register_blueprint(demo_api_bp)

    @app.before_request
    def limit_api_requests():
        if not request.path.startswith("/api/"):
            return
        user = session.get("user") or {}
        client_key = str(user.get("id") or user.get("username") or request.remote_addr or "unknown")
        allowed, remaining, retry_after = current_app.extensions["api_rate_limiter"].allow(client_key)
        g.api_rate_limit_remaining = remaining
        if not allowed:
            response = jsonify(
                {
                    "ok": False,
                    "error": "Demasiadas solicitudes. Espera antes de volver a consultar.",
                    "code": "rate_limit_exceeded",
                }
            )
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response

    @app.before_request
    def require_login():
        exempt_routes = ["auth.login", "static", "main.health"]

        token = session.get("access_token")
        if token:
            client = current_app.extensions.get("api_client")
            if client:
                client.set_user_token(token)

        if request.endpoint is None:
            return

        local_demo_api = (
            os.getenv("APP_ENV", "production").lower() == "local"
            and os.getenv("LOCAL_DEMO_AUTH", "0") == "1"
            and request.path.startswith("/api/v1/sites")
        )
        public_demo_read = request.method in ("GET", "OPTIONS") and request.path.startswith("/api/v1/sites")
        if request.endpoint not in exempt_routes and not public_demo_read and not local_demo_api and "user" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": "Autenticacion requerida."}), 401
            return redirect(url_for("auth.login"))

    @app.after_request
    def allow_demo_frontend(response):
        if hasattr(g, "api_rate_limit_remaining"):
            response.headers["X-RateLimit-Remaining"] = str(g.api_rate_limit_remaining)
        if request.path.startswith("/api/v1/sites"):
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
        return response

    return app
