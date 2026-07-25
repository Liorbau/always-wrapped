"""Application factory: wiring only — no routes, no business logic here."""

import os

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from app.errors import AppError, INTERNAL_ERROR, NOT_FOUND, error_payload
from core.logging import configure_logger

logger = configure_logger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app():
    # Blueprints are imported inside the factory: they import app.errors, which
    # would re-enter this module at import time.
    from app.modules.agent_api.router import agents_bp
    from app.modules.music.router import music_bp
    from app.modules.pages.router import pages_bp
    from app.modules.wrapped.router import wrapped_bp

    app = Flask(
        __name__,
        template_folder=os.path.join(PROJECT_ROOT, "templates"),
        static_folder=os.path.join(PROJECT_ROOT, "static"),
    )
    app.register_blueprint(pages_bp)
    app.register_blueprint(music_bp)
    app.register_blueprint(wrapped_bp)
    app.register_blueprint(agents_bp)
    register_error_handlers(app)
    return app


def register_error_handlers(app):
    @app.errorhandler(AppError)
    def _app_error(exc):
        return jsonify(exc.to_payload()), exc.status

    @app.errorhandler(HTTPException)
    def _http_error(exc):
        code = NOT_FOUND if exc.code == 404 else INTERNAL_ERROR
        return jsonify(error_payload(code, exc.description)), exc.code

    @app.errorhandler(Exception)
    def _unexpected(exc):
        logger.exception("Unhandled error: %s", exc)
        return jsonify(
            error_payload(INTERNAL_ERROR, "Something broke on our side.")
        ), 500

    return app
