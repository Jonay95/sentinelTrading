"""
Implementaciones concretas de los puertos de persistencia (adaptadores secundarios).

Una sesión SQLAlchemy se inyecta por constructor (Dependency Injection / SOLID-D).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.domain.dto import (
    AssetReadDto,
    NewsArticleRawDto,
    PredictionDueDto,
    QuoteBarDto,
)
from app.domain.value_objects import Signal
from app.infrastructure.persistence import orm_models as m

logger = logging.getLogger(__name__)


def _to_asset_dto(a: m.Asset) -> AssetReadDto:
    return AssetReadDto(
        id=a.id,
        symbol=a.symbol,
        name=a.name,
        asset_type=a.asset_type.value,
        external_id=a.external_id,
        provider=a.provider,
        news_keywords=a.news_keywords,
    )


class SqlAlchemyAssetRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def list_all_ordered_by_symbol(self) -> list[AssetReadDto]:
        rows = self._s.query(m.Asset).order_by(m.Asset.symbol).all()
        return [_to_asset_dto(a) for a in rows]

    def get_by_id(self, asset_id: int) -> AssetReadDto | None:
        a = self._s.get(m.Asset, asset_id)
        return _to_asset_dto(a) if a else None

    def count(self) -> int:
        return self._s.query(m.Asset).count()


class SqlAlchemyQuoteRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def list_by_asset_chronological(self, asset_id: int) -> list[QuoteBarDto]:
        rows = (
            self._s.query(m.Quote)
            .filter_by(asset_id=asset_id)
            .order_by(m.Quote.ts.asc())
            .all()
        )
        return [
            QuoteBarDto(
                ts=r.ts,
                close=r.close,
                open=r.open,
                high=r.high,
                low=r.low,
                volume=r.volume,
            )
            for r in rows
        ]

    def upsert_bars(self, asset_id: int, bars: list[QuoteBarDto]) -> int:
        n = 0
        for b in bars:
            q = self._s.query(m.Quote).filter_by(asset_id=asset_id, ts=b.ts).first()
            if q is None:
                q = m.Quote(asset_id=asset_id, ts=b.ts)
                self._s.add(q)
            q.open = b.open
            q.high = b.high
            q.low = b.low
            q.close = b.close
            q.volume = b.volume
            n += 1
        self._s.commit()
        return n

    def first_close_on_or_after(self, asset_id: int, moment: datetime) -> QuoteBarDto | None:
        r = (
            self._s.query(m.Quote)
            .filter(m.Quote.asset_id == asset_id, m.Quote.ts >= moment)
            .order_by(m.Quote.ts.asc())
            .first()
        )
        if not r:
            return None
        return QuoteBarDto(
            ts=r.ts, close=r.close, open=r.open, high=r.high, low=r.low, volume=r.volume
        )

    def last_close_on_or_before(self, asset_id: int, moment: datetime) -> QuoteBarDto | None:
        r = (
            self._s.query(m.Quote)
            .filter(m.Quote.asset_id == asset_id, m.Quote.ts <= moment)
            .order_by(m.Quote.ts.desc())
            .first()
        )
        if not r:
            return None
        return QuoteBarDto(
            ts=r.ts, close=r.close, open=r.open, high=r.high, low=r.low, volume=r.volume
        )

    def latest_bar(self, asset_id: int) -> QuoteBarDto | None:
        r = (
            self._s.query(m.Quote)
            .filter_by(asset_id=asset_id)
            .order_by(m.Quote.ts.desc())
            .first()
        )
        if not r:
            return None
        return QuoteBarDto(
            ts=r.ts, close=r.close, open=r.open, high=r.high, low=r.low, volume=r.volume
        )


class SqlAlchemyPredictionRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(
        self,
        *,
        asset_id: int,
        horizon_days: int,
        target_date: datetime,
        base_price: float,
        predicted_value: float,
        signal: str,
        confidence: float,
        model_version: str,
        features_json: dict[str, Any] | None,
    ) -> int:
        try:
            sig = Signal(signal)
        except ValueError:
            sig = Signal.hold
        p = m.Prediction(
            asset_id=asset_id,
            horizon_days=horizon_days,
            target_date=target_date,
            base_price=base_price,
            predicted_value=predicted_value,
            signal=sig,
            confidence=confidence,
            model_version=model_version,
            features_json=features_json,
        )
        self._s.add(p)
        self._s.flush()
        pid = p.id
        self._s.commit()
        return pid

    def recent_evaluated_errors(
        self, asset_id: int, model_version: str, limit: int
    ) -> list[tuple[float, float, float]]:
        q = (
            self._s.query(m.Prediction, m.PredictionOutcome)
            .join(m.PredictionOutcome, m.PredictionOutcome.prediction_id == m.Prediction.id)
            .filter(
                m.Prediction.asset_id == asset_id,
                m.Prediction.model_version == model_version,
            )
            .order_by(m.Prediction.created_at.desc())
            .limit(limit)
            .all()
        )
        out: list[tuple[float, float, float]] = []
        for pred, outc in q:
            out.append((pred.base_price, pred.predicted_value, outc.actual_value))
        return out

    def list_due_without_outcome(self, now: datetime) -> list[PredictionDueDto]:
        rows = (
            self._s.query(m.Prediction)
            .outerjoin(
                m.PredictionOutcome,
                m.PredictionOutcome.prediction_id == m.Prediction.id,
            )
            .filter(m.Prediction.target_date <= now, m.PredictionOutcome.id.is_(None))
            .all()
        )
        return [
            PredictionDueDto(
                id=p.id,
                asset_id=p.asset_id,
                target_date=p.target_date,
                base_price=p.base_price,
                predicted_value=p.predicted_value,
            )
            for p in rows
        ]

    def save_outcome(
        self,
        prediction_id: int,
        actual_value: float,
        metrics_json: dict[str, Any],
    ) -> None:
        o = m.PredictionOutcome(
            prediction_id=prediction_id,
            actual_value=actual_value,
            metrics_json=metrics_json,
        )
        self._s.add(o)

    def commit(self) -> None:
        self._s.commit()

    def latest_for_asset(self, asset_id: int) -> dict[str, Any] | None:
        p = (
            self._s.query(m.Prediction)
            .filter_by(asset_id=asset_id)
            .order_by(m.Prediction.created_at.desc())
            .first()
        )
        if not p:
            return None
        return {
            "id": p.id,
            "created_at": p.created_at.isoformat(),
            "signal": p.signal.value,
            "confidence": p.confidence,
            "base_price": p.base_price,
            "predicted_value": p.predicted_value,
            "target_date": p.target_date.isoformat(),
            "model_version": p.model_version,
        }


class SqlAlchemyNewsReadRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def average_sentiment(self, asset_id: int, hours: int) -> float | None:
        since = datetime.utcnow() - timedelta(hours=hours)
        rows = (
            self._s.query(m.NewsSentiment.compound_score)
            .join(m.NewsItem, m.NewsItem.id == m.NewsSentiment.news_item_id)
            .join(m.news_asset, m.news_asset.c.news_item_id == m.NewsItem.id)
            .filter(
                m.news_asset.c.asset_id == asset_id,
                m.NewsItem.published_at >= since,
            )
            .all()
        )
        if not rows:
            return None
        vals = [r[0] for r in rows]
        return sum(vals) / len(vals)

    def count_fetches_since(self, asset_id: int, hours: int) -> int:
        if hours <= 0:
            return 0
        since = datetime.utcnow() - timedelta(hours=hours)
        return (
            self._s.query(m.NewsItem)
            .join(m.news_asset, m.news_asset.c.news_item_id == m.NewsItem.id)
            .filter(
                m.news_asset.c.asset_id == asset_id,
                m.NewsItem.fetched_at >= since,
            )
            .count()
        )


class SqlAlchemyNewsWriteRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def persist_articles_for_asset(
        self, asset_id: int, articles: list[NewsArticleRawDto], compound_scores: list[float]
    ) -> int:
        asset = self._s.get(m.Asset, asset_id)
        if not asset:
            return 0
        if len(compound_scores) != len(articles):
            raise ValueError("compound_scores debe alinear con articles")
        n = 0
        for art, score in zip(articles, compound_scores):
            url = (art.url or "").strip()
            title = art.title[:512]
            existing = None
            if url:
                existing = self._s.query(m.NewsItem).filter(m.NewsItem.url == url[:1024]).first()
            if existing is None:
                existing = self._s.query(m.NewsItem).filter_by(title=title).first()
            if existing:
                if asset not in existing.assets:
                    existing.assets.append(asset)
                    self._s.commit()
                continue
            item = m.NewsItem(
                published_at=art.published_at,
                title=title,
                url=url[:1024] if url else None,
                source=art.source,
                snippet=art.snippet,
            )
            item.sentiment = m.NewsSentiment(news_item=item, compound_score=score)
            item.assets.append(asset)
            self._s.add(item)
            n += 1
        self._s.commit()
        return n
