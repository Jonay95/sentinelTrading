"""
Puertos hacia sistemas externos (APIs de mercado y noticias).

Cumplen el principio Open/Closed: nuevos proveedores = nuevos adaptadores sin tocar casos de uso.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.dto import AssetReadDto, NewsArticleRawDto, QuoteBarDto


@runtime_checkable
class IMarketHistoryGateway(Protocol):
    """Descarga histórico OHLCV (o cierre) para un activo según su proveedor."""

    def fetch_history(self, asset: AssetReadDto) -> list[QuoteBarDto]: ...


@runtime_checkable
class INewsRemoteSource(Protocol):
    """Una fuente remota de artículos (NewsAPI, Finnhub, etc.)."""

    def fetch(self, query: str) -> list[NewsArticleRawDto]: ...


@runtime_checkable
class ISentimentScorer(Protocol):
    """Transforma texto en un score numérico (ej. compound VADER)."""

    def score(self, text: str) -> float: ...


@runtime_checkable
class INewsAggregator(Protocol):
    """Agrega artículos de una o más fuentes remotas para un activo."""

    def fetch_for_asset(self, asset: AssetReadDto) -> list[NewsArticleRawDto]: ...
