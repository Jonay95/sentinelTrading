"""
DTOs de frontera usados por puertos del dominio.

Evitan que la capa de dominio dependa de la aplicación (aciclidad).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AssetReadDto:
    id: int
    symbol: str
    name: str
    asset_type: str
    external_id: str | None
    provider: str
    news_keywords: str | None


@dataclass(frozen=True)
class QuoteBarDto:
    ts: datetime
    close: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None


@dataclass(frozen=True)
class NewsArticleRawDto:
    published_at: datetime
    title: str
    url: str | None
    source: str | None
    snippet: str | None


@dataclass(frozen=True)
class PredictionDueDto:
    """Predicción vencida pendiente de evaluar frente al mercado real."""

    id: int
    asset_id: int
    target_date: datetime
    base_price: float
    predicted_value: float
