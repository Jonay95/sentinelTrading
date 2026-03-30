"""
Consultas de métricas agregadas (lado lectura).

Vive en infraestructura porque usa SQLAlchemy directamente; la API no construye SQL.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.infrastructure.persistence import orm_models as m


class MetricsQueryService:
    def __init__(self, session: Session) -> None:
        self._s = session

    def summary(self, days: int = 90) -> dict:
        since = datetime.utcnow() - timedelta(days=days)
        q = (
            self._s.query(
                m.Prediction.model_version,
                func.count(m.PredictionOutcome.id).label("n"),
                func.avg(
                    (func.abs(m.Prediction.predicted_value - m.PredictionOutcome.actual_value))
                    / func.nullif(m.Prediction.base_price, 0)
                ).label("mape_proxy"),
            )
            .join(m.PredictionOutcome, m.PredictionOutcome.prediction_id == m.Prediction.id)
            .filter(m.Prediction.created_at >= since)
            .group_by(m.Prediction.model_version)
            .all()
        )
        versions = [
            {
                "model_version": row.model_version,
                "count": int(row.n or 0),
                "mean_abs_pct_error": float(row.mape_proxy or 0),
            }
            for row in q
        ]
        return {"since": since.isoformat(), "by_version": versions}

    def by_asset(self, days: int = 90) -> list[dict]:
        since = datetime.utcnow() - timedelta(days=days)
        rows = (
            self._s.query(
                m.Asset.id,
                m.Asset.symbol,
                func.count(m.PredictionOutcome.id).label("n"),
                func.avg(
                    (func.abs(m.Prediction.predicted_value - m.PredictionOutcome.actual_value))
                    / func.nullif(m.Prediction.base_price, 0)
                ).label("mape"),
            )
            .join(m.Prediction, m.Prediction.asset_id == m.Asset.id)
            .join(m.PredictionOutcome, m.PredictionOutcome.prediction_id == m.Prediction.id)
            .filter(m.Prediction.created_at >= since)
            .group_by(m.Asset.id, m.Asset.symbol)
            .all()
        )
        return [
            {
                "asset_id": r.id,
                "symbol": r.symbol,
                "evaluated_predictions": int(r.n or 0),
                "mean_abs_pct_error": float(r.mape or 0),
            }
            for r in rows
        ]

    def best_model_version(self, days: int = 90) -> dict | None:
        data = self.summary(days=min(days, 365))
        versions = data.get("by_version") or []
        if not versions:
            return None
        best = min(versions, key=lambda v: v.get("mean_abs_pct_error") or 1.0)
        return {
            "recommended_version": best["model_version"],
            "mean_abs_pct_error": best["mean_abs_pct_error"],
            "sample_count": best["count"],
            "all_versions": versions,
        }
