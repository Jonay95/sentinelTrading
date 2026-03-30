"""
Casos de uso (Application Services).

Cada clase tiene una responsabilidad (SRP) y recibe dependencias por constructor (DIP).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from app.domain.dto import AssetReadDto
from app.domain.ports.gateways import IMarketHistoryGateway, INewsAggregator, ISentimentScorer
from app.domain.ports.repositories import (
    IAssetRepository,
    INewsReadRepository,
    INewsWriteRepository,
    IPredictionRepository,
    IQuoteRepository,
)
from app.domain.services import prediction_model
from app.domain.value_objects import Signal

if TYPE_CHECKING:
    from app.config import Config

logger = logging.getLogger(__name__)


def _historical_mae_directional(
    rows: list[tuple[float, float, float]],
) -> tuple[float, float]:
    """A partir de (base, predicho, real) ya evaluados, error medio y acierto direccional."""
    if not rows:
        return 0.02, 0.5
    maes: list[float] = []
    correct_dir = 0
    for base, pred_val, actual in rows:
        if base <= 0:
            continue
        pred_ret = (pred_val - base) / base
        actual_ret = (actual - base) / base
        maes.append(abs(pred_ret - actual_ret))
        if (pred_ret >= 0) == (actual_ret >= 0):
            correct_dir += 1
    mae = float(np.mean(maes)) if maes else 0.02
    acc = correct_dir / len(rows) if rows else 0.5
    return mae, acc


def _quotes_to_frames(bars: list[Any]) -> tuple[pd.Series, pd.Series | None]:
    if not bars:
        return pd.Series(dtype=float), None
    idx = pd.DatetimeIndex([b.ts for b in bars])
    close = pd.Series([b.close for b in bars], index=idx)
    vols = [b.volume for b in bars]
    if all(v is None for v in vols):
        return close, None
    volume = pd.Series([float(v) if v is not None else 0.0 for v in vols], index=idx)
    return close, volume


def _raw_signal(base: float, predicted: float, threshold_pct: float) -> Signal:
    if base <= 0:
        return Signal.hold
    chg = (predicted - base) / base
    if chg > threshold_pct:
        return Signal.buy
    if chg < -threshold_pct:
        return Signal.sell
    return Signal.hold


def _sentiment_multiplier(avg: float | None) -> float:
    if avg is None:
        return 1.0
    return 1.0 + 0.15 * max(-1.0, min(1.0, avg))


def _apply_sentiment_to_signal(signal: Signal, sentiment_mult: float) -> Signal:
    if sentiment_mult < 0.92 and signal == Signal.buy:
        return Signal.hold
    if sentiment_mult > 1.08 and signal == Signal.sell:
        return Signal.hold
    return signal


class IngestMarketDataUseCase:
    """Descarga histórico remoto y persiste cotizaciones (orquestación)."""

    def __init__(
        self,
        assets: IAssetRepository,
        quotes: IQuoteRepository,
        market: IMarketHistoryGateway,
    ) -> None:
        self._assets = assets
        self._quotes = quotes
        self._market = market

    def execute(self) -> dict[str, int]:
        results: dict[str, int] = {}
        for a in self._assets.list_all_ordered_by_symbol():
            try:
                bars = self._market.fetch_history(a)
                n = self._quotes.upsert_bars(a.id, bars)
                results[a.symbol] = n
            except Exception as e:
                logger.exception("Ingest failed for %s: %s", a.symbol, e)
                results[a.symbol] = -1
        return results


class IngestNewsUseCase:
    """Obtiene noticias remotas, calcula sentimiento y persiste con deduplicación."""

    def __init__(
        self,
        config: type,
        assets: IAssetRepository,
        news_read: INewsReadRepository,
        news_write: INewsWriteRepository,
        aggregator: INewsAggregator,
        scorer: ISentimentScorer,
    ) -> None:
        self._config = config
        self._assets = assets
        self._news_read = news_read
        self._news_write = news_write
        self._aggregator = aggregator
        self._scorer = scorer

    def execute(self, *, force: bool = False) -> dict[str, int]:
        counts: dict[str, int] = {}
        for asset in self._assets.list_all_ordered_by_symbol():
            if (
                not force
                and self._config.NEWS_MIN_INTERVAL_HOURS > 0
                and self._news_read.count_fetches_since(asset.id, self._config.NEWS_MIN_INTERVAL_HOURS)
                >= 1
            ):
                counts[asset.symbol] = 0
                logger.info(
                    "Noticias omitidas para %s (intervalo %sh)",
                    asset.symbol,
                    self._config.NEWS_MIN_INTERVAL_HOURS,
                )
                continue
            articles = self._aggregator.fetch_for_asset(asset)
            texts = [f"{x.title} {x.snippet or ''}" for x in articles]
            scores = [self._scorer.score(t) for t in texts]
            try:
                counts[asset.symbol] = self._news_write.persist_articles_for_asset(
                    asset.id, articles, scores
                )
            except Exception as e:
                logger.exception("News ingest %s: %s", asset.symbol, e)
                counts[asset.symbol] = -1
        return counts


class RunPredictionsUseCase:
    """Genera y persiste predicciones para todos los activos."""

    def __init__(
        self,
        config: type,
        assets: IAssetRepository,
        quotes: IQuoteRepository,
        predictions: IPredictionRepository,
        news_read: INewsReadRepository,
    ) -> None:
        self._config = config
        self._assets = assets
        self._quotes = quotes
        self._predictions = predictions
        self._news_read = news_read

    def _run_one(self, asset: AssetReadDto, model_version: str) -> int | None:
        bars = self._quotes.list_by_asset_chronological(asset.id)
        close, volume = _quotes_to_frames(bars)
        if close.empty:
            return None

        base = float(close.iloc[-1])
        thr = prediction_model.adaptive_threshold_pct(
            close,
            self._config.THRESHOLD_BASE_PCT,
            self._config.VOL_THRESHOLD_MULTIPLIER,
            self._config.THRESHOLD_MAX_PCT,
        )
        predicted_raw, feat = prediction_model.predict_next_price(
            close,
            volume,
            ensemble=self._config.PRED_ENSEMBLE,
            momentum_blend=self._config.MOMENTUM_BLEND,
        )
        feat["threshold_pct_used"] = thr
        feat["threshold_base_pct"] = self._config.THRESHOLD_BASE_PCT
        feat["market_features"] = prediction_model.compute_market_features(close, volume)

        raw_sig = _raw_signal(base, predicted_raw, thr)
        sent_mult = _sentiment_multiplier(self._news_read.average_sentiment(asset.id, 72))
        feat["sentiment_multiplier"] = sent_mult
        feat["raw_signal"] = raw_sig.value

        adjusted_pred = base + (predicted_raw - base) * sent_mult
        signal = _apply_sentiment_to_signal(raw_sig, sent_mult)

        extreme = prediction_model.is_extreme_volatility(close)
        if extreme:
            if signal != Signal.hold:
                signal = Signal.hold
            feat["extreme_volatility_override"] = True
            feat["signal_before_vol_filter"] = raw_sig.value

        hist = self._predictions.recent_evaluated_errors(asset.id, model_version, 20)
        mae_hist, dir_acc = _historical_mae_directional(hist)
        confidence = max(0.1, min(0.95, dir_acc * (1.0 - min(mae_hist, 0.2) * 5)))
        if extreme:
            confidence *= self._config.HIGH_VOL_CONFIDENCE_PENALTY
            confidence = min(confidence, 0.45)

        horizon = self._config.HORIZON_DAYS
        target_date = datetime.utcnow() + timedelta(days=horizon)

        return self._predictions.save(
            asset_id=asset.id,
            horizon_days=horizon,
            target_date=target_date,
            base_price=base,
            predicted_value=adjusted_pred,
            signal=signal.value,
            confidence=max(0.05, min(0.95, confidence)),
            model_version=model_version,
            features_json=feat,
        )

    def execute(self, model_version: str) -> list[int]:
        ids: list[int] = []
        for asset in self._assets.list_all_ordered_by_symbol():
            try:
                pid = self._run_one(asset, model_version)
                if pid is not None:
                    ids.append(pid)
            except Exception as e:
                logger.exception("Prediction failed for %s: %s", asset.symbol, e)
        return ids


class EvaluatePredictionsUseCase:
    """Cierra predicciones vencidas con el precio observado en cotizaciones."""

    def __init__(self, predictions: IPredictionRepository, quotes: IQuoteRepository) -> None:
        self._predictions = predictions
        self._quotes = quotes

    def execute(self) -> int:
        now = datetime.utcnow()
        pending = self._predictions.list_due_without_outcome(now)
        count = 0
        for p in pending:
            q = self._quotes.first_close_on_or_after(p.asset_id, p.target_date)
            if q is None:
                q = self._quotes.last_close_on_or_before(p.asset_id, now)
            if q is None:
                continue
            actual = q.close
            base = p.base_price
            pred_ret = (p.predicted_value - base) / base if base else 0.0
            actual_ret = (actual - base) / base if base else 0.0
            mae_pct = abs(pred_ret - actual_ret)
            directional_ok = (pred_ret >= 0) == (actual_ret >= 0)
            metrics = {
                "mae_return": float(mae_pct),
                "predicted_return": float(pred_ret),
                "actual_return": float(actual_ret),
                "directional_correct": directional_ok,
                "quote_ts": q.ts.isoformat(),
            }
            self._predictions.save_outcome(p.id, actual, metrics)
            count += 1
        self._predictions.commit()
        return count


class GetDashboardUseCase:
    """Compone la vista de panel a partir de repositorios de lectura."""

    def __init__(
        self,
        assets: IAssetRepository,
        quotes: IQuoteRepository,
        predictions: IPredictionRepository,
    ) -> None:
        self._assets = assets
        self._quotes = quotes
        self._predictions = predictions

    def execute(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for a in self._assets.list_all_ordered_by_symbol():
            item: dict[str, Any] = {
                "asset": {
                    "id": a.id,
                    "symbol": a.symbol,
                    "name": a.name,
                    "asset_type": a.asset_type,
                },
                "last_quote": None,
                "latest_prediction": None,
            }
            lq = self._quotes.latest_bar(a.id)
            if lq:
                item["last_quote"] = {"ts": lq.ts.isoformat(), "close": lq.close}
            lp = self._predictions.latest_for_asset(a.id)
            if lp:
                item["latest_prediction"] = lp
            out.append(item)
        return out


class FullPipelineUseCase:
    """Orquesta ingesta, noticias, predicción y evaluación en un solo flujo."""

    def __init__(
        self,
        ingest: IngestMarketDataUseCase,
        news: IngestNewsUseCase,
        predict: RunPredictionsUseCase,
        evaluate: EvaluatePredictionsUseCase,
        config: type,
    ) -> None:
        self._ingest = ingest
        self._news = news
        self._predict = predict
        self._evaluate = evaluate
        self._config = config

    def execute(self, *, force_news: bool = False) -> dict[str, Any]:
        ing = self._ingest.execute()
        nw = self._news.execute(force=force_news)
        mv = self._config.MODEL_VERSION
        pids = self._predict.execute(mv)
        ev = self._evaluate.execute()
        return {
            "ingested_rows_by_symbol": ing,
            "news_stored_by_symbol": nw,
            "prediction_ids": pids,
            "evaluated_predictions": ev,
            "model_version": mv,
            "force_news": force_news,
        }
