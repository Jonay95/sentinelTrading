"""Histórico de predicciones expuesto como JSON."""

from flask import jsonify, request

from app.api import api_bp
from app.container import get_container


@api_bp.get("/predictions")
def list_predictions():
    asset_id = request.args.get("asset_id", type=int)
    limit = request.args.get("limit", default=50, type=int)
    c = get_container()
    rows = c.api_reads.list_predictions(asset_id, min(limit, 200))
    return jsonify(rows)


@api_bp.get("/assets/<int:asset_id>/predictions")
def asset_predictions(asset_id):
    c = get_container()
    if not c.assets.get_by_id(asset_id):
        return jsonify({"error": "not found"}), 404
    limit = request.args.get("limit", default=100, type=int)
    rows = c.api_reads.list_predictions(asset_id, min(limit, 500))
    return jsonify(rows)
