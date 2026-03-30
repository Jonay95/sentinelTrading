"""
Consultas para endpoints HTTP (listados con filtros).

Concentran SQL específico de presentación para mantener los controladores delgados.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.infrastructure.persistence import orm_models as m


class ApiReadQueries:
    def __init__(self, session: Session) -> None:
        self._s = session

    def list_predictions(self, asset_id: int | None, limit: int) -> list[dict]:
        q = self._s.query(m.Prediction)
        if asset_id is not None:
            q = q.filter_by(asset_id=asset_id)
        rows = q.order_by(m.Prediction.created_at.desc()).limit(limit).all()
        out = []
        for p in rows:
            d = {
                "id": p.id,
                "asset_id": p.asset_id,
                "created_at": p.created_at.isoformat(),
                "horizon_days": p.horizon_days,
                "target_date": p.target_date.isoformat(),
                "base_price": p.base_price,
                "predicted_value": p.predicted_value,
                "signal": p.signal.value,
                "confidence": p.confidence,
                "model_version": p.model_version,
                "features": p.features_json,
                "outcome": None,
            }
            if p.outcome:
                d["outcome"] = {
                    "actual_value": p.outcome.actual_value,
                    "evaluated_at": p.outcome.evaluated_at.isoformat(),
                    "metrics": p.outcome.metrics_json,
                }
            out.append(d)
        return out

    def list_news_for_asset(self, asset_id: int, days: int = 7, limit: int = 50) -> list[dict]:
        since = datetime.utcnow() - timedelta(days=days)
        rows = (
            self._s.query(m.NewsItem)
            .join(m.news_asset)
            .filter(
                m.news_asset.c.asset_id == asset_id,
                m.NewsItem.published_at >= since,
            )
            .order_by(m.NewsItem.published_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": n.id,
                "published_at": n.published_at.isoformat(),
                "title": n.title,
                "url": n.url,
                "source": n.source,
                "snippet": n.snippet,
                "sentiment": n.sentiment.compound_score if n.sentiment else None,
            }
            for n in rows
        ]

    def list_quotes(
        self,
        asset_id: int,
        start: datetime | None,
        end: datetime | None,
        limit: int = 2000,
    ) -> list[dict]:
        q = self._s.query(m.Quote).filter_by(asset_id=asset_id)
        if start:
            q = q.filter(m.Quote.ts >= start)
        if end:
            q = q.filter(m.Quote.ts <= end)
        rows = q.order_by(m.Quote.ts.asc()).limit(limit).all()
        return [
            {
                "ts": r.ts.isoformat(),
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
            }
            for r in rows
        ]
