"""
Adaptadores de datos de mercado (CoinGecko, Yahoo vía yfinance).

Implementan el puerto IMarketHistoryGateway; el caso de uso no conoce URLs ni JSON.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import requests
import yfinance as yf

from app.domain.dto import AssetReadDto, QuoteBarDto
from app.domain.value_objects import AssetType

if TYPE_CHECKING:
    from app.config import Config

logger = logging.getLogger(__name__)


class CoinGeckoHistoryAdapter:
    """Cliente HTTP para el endpoint market_chart de CoinGecko."""

    def fetch_daily(self, coingecko_id: str, days: int) -> list[QuoteBarDto]:
        n_days = min(max(int(days), 1), 365)
        url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}/market_chart"
        r = requests.get(
            url,
            params={"vs_currency": "usd", "days": n_days, "interval": "daily"},
            timeout=45,
        )
        r.raise_for_status()
        data = r.json()
        prices = data.get("prices") or []
        volumes = data.get("total_volumes") or []
        vol_by_ts = {int(ts_ms): float(vol) for ts_ms, vol in volumes if vol is not None}
        out: list[QuoteBarDto] = []
        for ts_ms, close in prices:
            ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).replace(tzinfo=None)
            v = vol_by_ts.get(int(ts_ms))
            out.append(
                QuoteBarDto(
                    ts=ts,
                    close=float(close),
                    open=None,
                    high=None,
                    low=None,
                    volume=v,
                )
            )
        return out


class YahooFinanceHistoryAdapter:
    """Histórico diario usando la librería yfinance (no oficial)."""

    def fetch(self, ticker: str, period: str) -> list[QuoteBarDto]:
        t = yf.Ticker(ticker)
        hist = t.history(period=period, interval="1d", auto_adjust=True)
        if hist.empty:
            return []
        out: list[QuoteBarDto] = []
        for idx, row in hist.iterrows():
            ts = idx.to_pydatetime()
            if ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)
            out.append(
                QuoteBarDto(
                    ts=ts,
                    open=float(row["Open"]) if row["Open"] == row["Open"] else None,
                    high=float(row["High"]) if row["High"] == row["High"] else None,
                    low=float(row["Low"]) if row["Low"] == row["Low"] else None,
                    close=float(row["Close"]),
                    volume=float(row["Volume"]) if row["Volume"] == row["Volume"] else None,
                )
            )
        return out


class CompositeMarketHistoryGateway:
    """
    Selecciona el adaptador según tipo de activo y proveedor (Strategy implícita).
    """

    def __init__(self, config: type, coingecko: CoinGeckoHistoryAdapter, yahoo: YahooFinanceHistoryAdapter) -> None:
        self._config = config
        self._cg = coingecko
        self._yh = yahoo

    def fetch_history(self, asset: AssetReadDto) -> list[QuoteBarDto]:
        if asset.asset_type == AssetType.crypto.value and asset.external_id:
            return self._cg.fetch_daily(asset.external_id, self._config.COINGECKO_DAYS)
        if asset.provider == "yahoo" and asset.external_id:
            return self._yh.fetch(asset.external_id, self._config.YFINANCE_PERIOD)
        logger.warning("Sin ruta de mercado para activo %s", asset.symbol)
        return []
