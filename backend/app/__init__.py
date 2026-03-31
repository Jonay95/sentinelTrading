"""
Aplicación Flask: fábrica `create_app`, CORS, registro de blueprints y arranque de BD/seed.

La lógica de negocio no vive aquí; véase `application/`, `domain/` e `infrastructure/`.
"""

import logging

from flask import Flask
from flask_cors import CORS

from sqlalchemy import inspect

from app.config import Config
from app.extensions import db, migrate, mail
from app.seed import seed_assets_if_empty

logger = logging.getLogger(__name__)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": config_class.CORS_ORIGINS}})

    from app.api import api_bp

    app.register_blueprint(api_bp)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    # Don't initialize database at startup to avoid connection issues
    # Database will be initialized on-demand when needed

    return app
