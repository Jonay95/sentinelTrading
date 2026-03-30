"""Métricas y walk-forward: lectura vía servicios de consulta de infraestructura / aplicación."""

from flask import jsonify, request

from app.api import api_bp
from app.container import get_container


@api_bp.get("/metrics/summary")
def metrics_summary():
    days = request.args.get("days", default=90, type=int)
    c = get_container()
    return jsonify(c.metrics_queries.summary(days=min(days, 365)))


@api_bp.get("/metrics/by-asset")
def metrics_by_asset():
    days = request.args.get("days", default=90, type=int)
    c = get_container()
    return jsonify(c.metrics_queries.by_asset(days=min(days, 365)))


@api_bp.get("/metrics/model-recommendation")
def model_recommendation():
    days = request.args.get("days", default=90, type=int)
    c = get_container()
    rec = c.metrics_queries.best_model_version(days=min(days, 365))
    return jsonify(rec or {"message": "sin predicciones evaluadas aún"})


@api_bp.get("/metrics/walk-forward")
def metrics_walk_forward():
    asset_id = request.args.get("asset_id", type=int)
    train_min = request.args.get("train_min", default=55, type=int)
    step = request.args.get("step", default=3, type=int)
    train_min = max(30, min(train_min, 500))
    step = max(1, min(step, 30))

    ens_raw = request.args.get("ensemble")
    ensemble: bool | None = None
    if ens_raw is not None:
        ensemble = str(ens_raw).lower() in ("1", "true", "yes", "on")

    c = get_container()
    if asset_id is not None:
        return jsonify(
            c.walk_forward.for_asset(
                asset_id,
                train_min=train_min,
                step=step,
                ensemble=ensemble,
            )
        )
    return jsonify(
        c.walk_forward.for_all_assets(
            train_min=train_min,
            step=step,
            ensemble=ensemble,
        )
    )
