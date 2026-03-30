"""Recursos REST de activos y series de cotizaciones."""

from datetime import datetime

from flask import jsonify, request

from app.api import api_bp
from app.container import get_container


@api_bp.get("/assets")
def list_assets():
    c = get_container()
    rows = c.assets.list_all_ordered_by_symbol()
    return jsonify(
        [
            {
                "id": a.id,
                "symbol": a.symbol,
                "name": a.name,
                "asset_type": a.asset_type,
                "provider": a.provider,
            }
            for a in rows
        ]
    )


@api_bp.get("/assets/<int:asset_id>")
def get_asset(asset_id):
    c = get_container()
    a = c.assets.get_by_id(asset_id)
    if not a:
        return jsonify({"error": "not found"}), 404
    return jsonify(
        {
            "id": a.id,
            "symbol": a.symbol,
            "name": a.name,
            "asset_type": a.asset_type,
            "provider": a.provider,
            "external_id": a.external_id,
        }
    )


@api_bp.get("/assets/<int:asset_id>/quotes")
def asset_quotes(asset_id):
    c = get_container()
    a = c.assets.get_by_id(asset_id)
    if not a:
        return jsonify({"error": "not found"}), 404
    start = request.args.get("start")
    end = request.args.get("end")
    start_dt = datetime.fromisoformat(start) if start else None
    end_dt = datetime.fromisoformat(end) if end else None
    data = c.api_reads.list_quotes(asset_id, start_dt, end_dt, limit=2000)
    return jsonify(data)
