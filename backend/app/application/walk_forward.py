"""
Análisis walk-forward: solo usa puertos y el modelo de dominio (sin escribir predicciones en BD).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from app.domain.ports.repositories import IAssetRepository, IQuoteRepository
from app.domain.services import prediction_model

if TYPE_CHECKING:
    from app.config import Config

logger = logging.getLogger(__name__)


class WalkForwardAnalysisService:
    """Validación histórica paso a paso (responsabilidad única: métricas fuera de muestra)."""

    def __init__(
        self,
        config: type,
        assets: IAssetRepository,
        quotes: IQuoteRepository,
    ) -> None:
        self._config = config
        self._assets = assets
        self._quotes = quotes

    def for_asset(
        self,
        asset_id: int,
        *,
        train_min: int = 55,
        step: int = 3,
        ensemble: bool | None = None,
    ) -> dict[str, Any]:
        cfg = self._config
        use_ensemble = cfg.PRED_ENSEMBLE if ensemble is None else ensemble
        bars = self._quotes.list_by_asset_chronological(asset_id)
        if len(bars) < train_min + 2:
            return {
                "asset_id": asset_id,
                "error": "insufficient_data",
                "n_quotes": len(bars),
                "train_min_required": train_min,
            }

        idx = pd.DatetimeIndex([b.ts for b in bars])
        closes = pd.Series([b.close for b in bars], index=idx)
        vols: pd.Series | None = None
        if any(b.volume is not None for b in bars):
            vols = pd.Series([float(b.volume or 0) for b in bars], index=idx)

        preds: list[float] = []
        actuals: list[float] = []
        bases: list[float] = []
        thr_used: list[float] = []

        for i in range(train_min, len(closes) - 1, step):
            sub_close = closes.iloc[: i + 1]
            sub_vol = vols.iloc[: i + 1] if vols is not None else None
            try:
                pred_price, _ = prediction_model.predict_next_price(
                    sub_close,
                    sub_vol,
                    ensemble=use_ensemble,
                    momentum_blend=cfg.MOMENTUM_BLEND,
                )
            except Exception as e:
                logger.debug("walk_forward step %s: %s", i, e)
                continue
            base = float(sub_close.iloc[-1])
            actual = float(closes.iloc[i + 1])
            thr = prediction_model.adaptive_threshold_pct(
                sub_close,
                cfg.THRESHOLD_BASE_PCT,
                cfg.VOL_THRESHOLD_MULTIPLIER,
                cfg.THRESHOLD_MAX_PCT,
            )
            preds.append(pred_price)
            actuals.append(actual)
            bases.append(base)
            thr_used.append(thr)

        if not preds:
            return {"asset_id": asset_id, "error": "no_predictions", "n_quotes": len(bars)}

        errs_pct = [abs(p - a) / a for p, a in zip(preds, actuals) if a > 0]
        dir_correct = sum(
            1 for b, p, a in zip(bases, preds, actuals) if (p >= b) == (a >= b)
        )
        signal_eval = []
        for b, p, a, thr in zip(bases, preds, actuals, thr_used):
            pred_sig = 1 if (p - b) / b > thr else (-1 if (p - b) / b < -thr else 0)
            actual_sig = 1 if (a - b) / b > thr else (-1 if (a - b) / b < -thr else 0)
            signal_eval.append(pred_sig == actual_sig)

        asset = self._assets.get_by_id(asset_id)
        return {
            "asset_id": asset_id,
            "symbol": asset.symbol if asset else None,
            "n_steps": len(preds),
            "train_min": train_min,
            "step": step,
            "ensemble": use_ensemble,
            "mean_abs_pct_error": float(np.mean(errs_pct)) if errs_pct else 0.0,
            "median_abs_pct_error": float(np.median(errs_pct)) if errs_pct else 0.0,
            "directional_accuracy": float(dir_correct / len(preds)),
            "signal_match_rate": float(np.mean(signal_eval)) if signal_eval else 0.0,
        }

    def for_all_assets(
        self,
        train_min: int = 55,
        step: int = 3,
        ensemble: bool | None = None,
    ) -> dict[str, Any]:
        out: list[dict[str, Any]] = []
        for a in self._assets.list_all_ordered_by_symbol():
            r = self.for_asset(a.id, train_min=train_min, step=step, ensemble=ensemble)
            if "error" not in r:
                out.append(r)
            else:
                out.append({**r, "symbol": a.symbol})
        return {"assets": out, "train_min": train_min, "step": step}
