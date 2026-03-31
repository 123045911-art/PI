import logging
import os

from flask import Flask, session, redirect, url_for, request

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
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "super-secret-key-123")

    # Extensiones
    api_client = VisioFlowApiClient()
    app.extensions["api_client"] = api_client
    
    print("DEBUG: Instantiating TrackerService...")
    tracker_service = TrackerService()
    app.extensions["tracker_service"] = tracker_service

    # Blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)

    @app.before_request
    def require_login():
        # Rutas que no requieren login
        exempt_routes = ["auth.login", "static", "main.health"]
        
        if request.endpoint is None:
            return # Permitir que Flask maneje 404 sin intentar redirigir

        if request.endpoint not in exempt_routes and "user" not in session:
            return redirect(url_for("auth.login"))

    return app
