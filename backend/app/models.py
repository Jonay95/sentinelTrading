"""
Modelos ORM y enums reexportados para compatibilidad (Alembic, seeds, imports legados).

La definición canónica de tablas está en `infrastructure.persistence.orm_models`;
los enums de negocio en `domain.value_objects`.
"""

from app.domain.value_objects import AssetType, Signal
from app.infrastructure.persistence.orm_models import (
    Asset,
    NewsItem,
    NewsSentiment,
    Prediction,
    PredictionOutcome,
    Quote,
    news_asset,
)

__all__ = [
    "Asset",
    "AssetType",
    "NewsItem",
    "NewsSentiment",
    "Prediction",
    "PredictionOutcome",
    "Quote",
    "Signal",
    "news_asset",
]
