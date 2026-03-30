"""
Fuentes remotas de noticias y scorer de sentimiento (VADER).

Separar fetch vs scoring respeta Single Responsibility.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from app.domain.dto import AssetReadDto, NewsArticleRawDto
from app.domain.value_objects import AssetType

if TYPE_CHECKING:
    from app.config import Config

logger = logging.getLogger(__name__)


class VaderSentimentScorer:
    """Adaptador de dominio ISentimentScorer usando VADER (inglés, rápido)."""

    def __init__(self) -> None:
        self._analyzer = SentimentIntensityAnalyzer()

    def score(self, text: str) -> float:
        if not text:
            return 0.0
        return float(self._analyzer.polarity_scores(text)["compound"])


class NewsApiRemoteSource:
    """Cliente NewsAPI (plan gratuito con límites)."""

    def __init__(self, config: type) -> None:
        self._config = config

    def fetch(self, keywords: str) -> list[NewsArticleRawDto]:
        key = self._config.NEWS_API_KEY
        if not key:
            return []
        url = "https://newsapi.org/v2/everything"
        from_date = (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d")
        ps = min(self._config.NEWS_PAGE_SIZE, 100)
        r = requests.get(
            url,
            params={
                "q": keywords,
                "from": from_date,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": ps,
                "apiKey": key,
            },
            timeout=25,
        )
        if r.status_code != 200:
            logger.warning("NewsAPI status %s", r.status_code)
            return []
        articles = (r.json().get("articles")) or []
        out: list[NewsArticleRawDto] = []
        for a in articles:
            pub = a.get("publishedAt")
            if not pub:
                continue
            try:
                ts = datetime.fromisoformat(pub.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                ts = datetime.utcnow()
            out.append(
                NewsArticleRawDto(
                    published_at=ts,
                    title=(a.get("title") or "")[:500],
                    url=a.get("url"),
                    source=(a.get("source") or {}).get("name"),
                    snippet=(a.get("description") or "")[:2000],
                )
            )
        return out


class FinnhubRemoteSource:
    """Noticias de empresa / mercado en Finnhub."""

    def __init__(self, config: type) -> None:
        self._config = config

    def fetch(self, symbol: str) -> list[NewsArticleRawDto]:
        key = self._config.FINNHUB_API_KEY
        if not key:
            return []
        from_d = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
        to_d = datetime.utcnow().strftime("%Y-%m-%d")
        r = requests.get(
            "https://finnhub.io/api/v1/company-news",
            params={"symbol": symbol, "from": from_d, "to": to_d, "token": key},
            timeout=25,
        )
        if r.status_code != 200:
            return []
        items = r.json() or []
        out: list[NewsArticleRawDto] = []
        for it in items[:30]:
            ts = datetime.utcfromtimestamp(it.get("datetime", 0))
            out.append(
                NewsArticleRawDto(
                    published_at=ts,
                    title=(it.get("headline") or "")[:500],
                    url=it.get("url"),
                    source="finnhub",
                    snippet=(it.get("summary") or "")[:2000],
                )
            )
        return out


class NewsAggregator:
    """
    Orquesta fuentes remotas según el activo (sin persistir).
    Usado por el caso de uso de ingesta de noticias.
    """

    def __init__(self, config: type, newsapi: NewsApiRemoteSource, finnhub: FinnhubRemoteSource) -> None:
        self._config = config
        self._newsapi = newsapi
        self._fh = finnhub

    def fetch_for_asset(self, asset: AssetReadDto) -> list[NewsArticleRawDto]:
        total: list[NewsArticleRawDto] = []
        kw = asset.news_keywords or asset.symbol
        total.extend(self._newsapi.fetch(kw))
        if asset.asset_type == AssetType.stock.value and self._config.FINNHUB_API_KEY:
            total.extend(self._fh.fetch(asset.symbol))
        elif asset.asset_type == AssetType.crypto.value and self._config.FINNHUB_API_KEY:
            total.extend(self._fh.fetch(f"BINANCE:{asset.symbol}USDT"))
        return total
