import logging
import os

from flask import Flask, session, redirect, url_for, request, current_app

from app.core.tracker_service import TrackerService
from app.core.api_client import VisioFlowApiClient
from app.routes import main_bp
from app.auth_routes import auth_bp
from app.user_routes import user_bp


def create_app() -> Flask:
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

    # Extensiones
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

    print("DEBUG: Instantiating TrackerService...")
    tracker_service = TrackerService(api_client=api_client)
    app.extensions["tracker_service"] = tracker_service

    # Blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)

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

        if request.endpoint not in exempt_routes and "user" not in session:
            return redirect(url_for("auth.login"))

    return app
