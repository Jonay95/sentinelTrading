"""Noticias asociadas a un activo (consulta de lectura)."""

from flask import jsonify

from app.api import api_bp
from app.container import get_container


@api_bp.get("/assets/<int:asset_id>/news")
def asset_news(asset_id):
    c = get_container()
    if not c.assets.get_by_id(asset_id):
        return jsonify({"error": "not found"}), 404
    rows = c.api_reads.list_news_for_asset(asset_id, days=7, limit=50)
    return jsonify(rows)
