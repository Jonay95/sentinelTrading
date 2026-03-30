"""
Modelo estadístico de precios (dominio): features, ARIMA, ETS, ensemble y umbrales.

Sin acceso a base de datos ni HTTP — solo series temporales. Así se puede probar
y reutilizar en backtest (Open/Closed: nuevos modelos sustituyen funciones aquí).
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import ExponentialSmoothing

logger = logging.getLogger(__name__)


def compute_market_features(
    close: pd.Series,
    volume: pd.Series | None = None,
) -> dict[str, Any]:
    """Volatilidad (desv. log-retornos 20d), momentum 5d/20d, ratio volumen 5d/20d."""
    c = close.astype(float).clip(lower=1e-12)
    logp = np.log(c)
    ret = logp.diff().dropna()
    vol_20 = float(ret.tail(min(20, len(ret))).std()) if len(ret) >= 3 else 0.01
    if not np.isfinite(vol_20) or vol_20 <= 0:
        vol_20 = 0.01

    mom_5 = float(c.iloc[-1] / c.iloc[-6] - 1) if len(c) >= 6 else 0.0
    mom_20 = float(c.iloc[-1] / c.iloc[-21] - 1) if len(c) >= 21 else 0.0

    vol_ratio: float | None = None
    if volume is not None and len(volume) == len(close):
        v = pd.to_numeric(volume, errors="coerce").fillna(0.0)
        if float(v.tail(20).sum()) > 0 and len(v) >= 20:
            vol_ratio = float(v.tail(5).mean() / (v.tail(20).mean() + 1e-9))

    return {
        "volatility_20d_logret": vol_20,
        "momentum_5d": mom_5,
        "momentum_20d": mom_20,
        "volume_ratio_5_20": vol_ratio,
    }


def adaptive_threshold_pct(
    close: pd.Series,
    base_pct: float,
    vol_mult: float,
    max_pct: float,
) -> float:
    feats = compute_market_features(close, None)
    v = feats["volatility_20d_logret"]
    thr = max(base_pct, vol_mult * float(v))
    return float(min(thr, max_pct))


def _predict_arima_one_step(close: pd.Series) -> tuple[float | None, dict[str, Any]]:
    meta: dict[str, Any] = {"method": "arima"}
    if len(close) < 15:
        meta["method"] = "last"
        return float(close.iloc[-1]), meta

    log_prices = np.log(close.astype(float).clip(lower=1e-12))
    returns = log_prices.diff().dropna()
    if len(returns) < 10:
        meta["method"] = "ma_short"
        return float(close.tail(5).mean()), meta

    try:
        model = ARIMA(returns, order=(1, 0, 1))
        fitted = model.fit()
        fc = fitted.forecast(steps=1)
        next_log_ret = float(fc.iloc[0]) if hasattr(fc, "iloc") else float(fc[0])
        last_log = float(log_prices.iloc[-1])
        pred = float(np.exp(last_log + next_log_ret))
        meta["aic"] = float(fitted.aic) if hasattr(fitted, "aic") and np.isfinite(fitted.aic) else None
        return pred, meta
    except Exception as e:
        logger.debug("ARIMA error: %s", e)
        meta["method"] = "arima_failed_ma"
        return float(close.tail(5).mean()), meta


def _predict_ets_one_step(close: pd.Series) -> tuple[float | None, dict[str, Any]]:
    meta: dict[str, Any] = {"method": "ets"}
    s = close.astype(float).clip(lower=1e-12)
    if len(s) < 10:
        meta["method"] = "ets_short"
        return float(s.iloc[-1]), meta
    try:
        model = ExponentialSmoothing(
            s.values,
            trend="add",
            seasonal=None,
            initialization_method="estimated",
        )
        fitted = model.fit(optimized=True)
        fc = fitted.forecast(1)
        val = float(fc[0]) if hasattr(fc, "__getitem__") else float(fc)
        if not np.isfinite(val) or val <= 0:
            return float(s.iloc[-1]), {**meta, "method": "ets_invalid"}
        return val, meta
    except Exception as e:
        logger.debug("ETS error: %s", e)
        meta["method"] = "ets_failed_last"
        return float(s.iloc[-1]), meta


def predict_next_price(
    close: pd.Series,
    volume: pd.Series | None,
    *,
    ensemble: bool = True,
    momentum_blend: float = 0.15,
) -> tuple[float, dict[str, Any]]:
    close = close.sort_index()
    if volume is not None and len(volume) == len(close):
        volume = volume.reindex(close.index)
    feats = compute_market_features(close, volume)

    pred_a, meta_a = _predict_arima_one_step(close)
    pred_e, meta_e = _predict_ets_one_step(close)
    assert pred_a is not None and pred_e is not None

    if ensemble and len(close) >= 20:
        raw = 0.5 * pred_a + 0.5 * pred_e
        blend_method = "ensemble_arima_ets"
    else:
        raw = pred_a
        blend_method = "arima_only" if not ensemble else "arima_short_series"

    mom = feats["momentum_5d"]
    nudge = 1.0 + momentum_blend * float(np.tanh(mom * 8))
    pred = float(raw * nudge)

    features: dict[str, Any] = {
        **feats,
        "pred_arima": pred_a,
        "pred_ets": pred_e,
        "pred_before_momentum": raw,
        "momentum_nudge_factor": nudge,
        "blend_method": blend_method,
        "arima_meta": meta_a,
        "ets_meta": meta_e,
    }
    return pred, features


def is_extreme_volatility(close: pd.Series, quantile_threshold: float = 0.9) -> bool:
    logp = np.log(close.astype(float).clip(lower=1e-12))
    ret = logp.diff().dropna()
    if len(ret) < 40:
        return False
    last_v = float(ret.tail(20).std())
    hist = [float(ret.iloc[i : i + 20].std()) for i in range(0, len(ret) - 20, 5)]
    if not hist:
        return False
    q = float(np.quantile(hist, quantile_threshold))
    return last_v > max(q, 1e-6)
