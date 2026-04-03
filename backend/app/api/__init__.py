from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api")

from app.api import assets, dashboard, jobs, metrics, news, predictions, dashboards  # noqa: E402, F401
