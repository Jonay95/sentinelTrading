"""Endpoints para disparar jobs manualmente (adaptadores de entrada)."""

from flask import jsonify, request

from app import config as app_config
from app.api import api_bp
from app.container import get_container


def _truthy(val: str | None) -> bool:
    return (val or "").lower() in ("1", "true", "yes", "on")


@api_bp.post("/jobs/ingest")
def job_ingest():
    c = get_container()
    return jsonify({"ingested_rows_by_symbol": c.ingest_market.execute()})


@api_bp.post("/jobs/predict")
def job_predict():
    c = get_container()
    mv = app_config.Config.MODEL_VERSION
    return jsonify({"prediction_ids": c.run_predictions.execute(mv), "model_version": mv})


@api_bp.post("/jobs/evaluate")
def job_evaluate():
    c = get_container()
    return jsonify({"evaluated": c.evaluate_predictions.execute()})


@api_bp.post("/jobs/news")
def job_news():
    force = _truthy(request.args.get("force"))
    c = get_container()
    r = c.ingest_news.execute(force=force)
    return jsonify({"stored_by_symbol": r, "force": force})


@api_bp.post("/jobs/full-pipeline")
def job_full_pipeline():
    force_news = _truthy(request.args.get("force_news"))
    c = get_container()
    return jsonify(c.full_pipeline.execute(force_news=force_news))
