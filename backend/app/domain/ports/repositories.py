"""
Puertos de persistencia (Repository pattern).

Las implementaciones viven en infrastructure.persistence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from app.domain.dto import (
    AssetReadDto,
    NewsArticleRawDto,
    PredictionDueDto,
    QuoteBarDto,
)


@runtime_checkable
class IAssetRepository(Protocol):
    """Lectura de activos configurados en el sistema."""

    def list_all_ordered_by_symbol(self) -> list[AssetReadDto]: ...

    def get_by_id(self, asset_id: int) -> AssetReadDto | None: ...

    def count(self) -> int: ...


@runtime_checkable
class IQuoteRepository(Protocol):
    """Series de cotizaciones y utilidades para evaluación."""

    def list_by_asset_chronological(self, asset_id: int) -> list[QuoteBarDto]: ...

    def upsert_bars(self, asset_id: int, bars: list[QuoteBarDto]) -> int: ...

    def first_close_on_or_after(self, asset_id: int, moment: datetime) -> QuoteBarDto | None: ...

    def last_close_on_or_before(self, asset_id: int, moment: datetime) -> QuoteBarDto | None: ...

    def latest_bar(self, asset_id: int) -> QuoteBarDto | None: ...


@runtime_checkable
class IPredictionRepository(Protocol):
    """Ciclo de vida de predicciones y métricas históricas."""

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
    ) -> int: ...

    def recent_evaluated_errors(
        self, asset_id: int, model_version: str, limit: int
    ) -> list[tuple[float, float, float]]:
        """(base_price, predicted_value, actual_value)."""

    def list_due_without_outcome(self, now: datetime) -> list[PredictionDueDto]: ...

    def save_outcome(
        self,
        prediction_id: int,
        actual_value: float,
        metrics_json: dict[str, Any],
    ) -> None: ...

    def commit(self) -> None: ...

    def latest_for_asset(self, asset_id: int) -> dict[str, Any] | None: ...


@runtime_checkable
class INewsReadRepository(Protocol):
    def average_sentiment(self, asset_id: int, hours: int) -> float | None: ...

    def count_fetches_since(self, asset_id: int, hours: int) -> int: ...


@runtime_checkable
class INewsWriteRepository(Protocol):
    def persist_articles_for_asset(
        self, asset_id: int, articles: list[NewsArticleRawDto], compound_scores: list[float]
    ) -> int: ...
