"""Controlador HTTP del panel: delega en el caso de uso (adaptador primario delgado)."""

from flask import jsonify

from app.api import api_bp
from app.container import get_container


@api_bp.get("/dashboard")
def dashboard():
    c = get_container()
    return jsonify(c.dashboard.execute())
