from flask import Flask

from app.core.tracker_service import TrackerService
from app.routes import main_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    tracker_service = TrackerService()
    app.extensions["tracker_service"] = tracker_service

    app.register_blueprint(main_bp)
    return app
