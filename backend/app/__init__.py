"""
Aplicación Flask: fábrica `create_app`, CORS, registro de blueprints y arranque de BD/seed.

La lógica de negocio no vive aquí; véase `application/`, `domain/` e `infrastructure/`.
"""

import logging

from flask import Flask
from flask_cors import CORS

from sqlalchemy import inspect

from app.config import Config
from app.extensions import db, migrate
from app.seed import seed_assets_if_empty

logger = logging.getLogger(__name__)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app, resources={r"/api/*": {"origins": config_class.CORS_ORIGINS}})

    from app.api import api_bp

    app.register_blueprint(api_bp)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    with app.app_context():
        if not inspect(db.engine).has_table("assets"):
            db.create_all()
        seed_assets_if_empty()

    return app
