"""
Graceful degradation strategies for handling external API failures.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
import pandas as pd

from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.resilience import ResilientAPIClient
from app.domain.dto import QuoteBarDto, NewsArticleRawDto

logger = logging.getLogger(__name__)


@dataclass
class DegradationLevel:
    """Represents a degradation level with fallback strategies."""
    level: int
    name: str
    description: str
    max_retry_attempts: int
    fallback_enabled: bool


class DegradationLevels:
    """Predefined degradation levels."""
    
    FULL = DegradationLevel(0, "FULL", "All services operational", 3, False)
    PARTIAL = DegradationLevel(1, "PARTIAL", "Some services degraded", 2, True)
    MINIMAL = DegradationLevel(2, "MINIMAL", "Minimal service available", 1, True)
    OFFLINE = DegradationLevel(3, "OFFLINE", "All external services unavailable", 0, True)


class FallbackDataManager(LoggerMixin):
    """Manages fallback data for graceful degradation."""
    
    def __init__(self):
        self._fallback_quotes: Dict[str, List[QuoteBarDto]] = {}
        self._fallback_news: Dict[str, List[NewsArticleRawDto]] = {}
        self._last_updated: Dict[str, datetime] = {}
        self._fallback_ttl_hours = 24  # Fallback data valid for 24 hours
    
    def store_quotes_fallback(self, symbol: str, quotes: List[QuoteBarDto]):
        """Store quotes as fallback data."""
        self._fallback_quotes[symbol] = quotes
        self._last_updated[symbol] = datetime.utcnow()
        self.logger.info(f"Stored fallback quotes for {symbol}: {len(quotes)} quotes")
    
    def get_quotes_fallback(self, symbol: str, limit: int = 100) -> Optional[List[QuoteBarDto]]:
        """Get fallback quotes if available and not expired."""
        if symbol not in self._fallback_quotes:
            return None
        
        # Check if fallback data is still valid
        last_updated = self._last_updated.get(symbol)
        if last_updated and (datetime.utcnow() - last_updated) > timedelta(hours=self._fallback_ttl_hours):
            self.logger.warning(f"Fallback data expired for {symbol}")
            return None
        
        quotes = self._fallback_quotes[symbol]
        return quotes[-limit:] if quotes else None
    
    def store_news_fallback(self, keywords: str, articles: List[NewsArticleRawDto]):
        """Store news articles as fallback data."""
        self._fallback_news[keywords] = articles
        self._last_updated[f"news_{keywords}"] = datetime.utcnow()
        self.logger.info(f"Stored fallback news for keywords '{keywords}': {len(articles)} articles")
    
    def get_news_fallback(self, keywords: str, limit: int = 50) -> Optional[List[NewsArticleRawDto]]:
        """Get fallback news if available and not expired."""
        if keywords not in self._fallback_news:
            return None
        
        # Check if fallback data is still valid
        last_updated = self._last_updated.get(f"news_{keywords}")
        if last_updated and (datetime.utcnow() - last_updated) > timedelta(hours=self._fallback_ttl_hours):
            self.logger.warning(f"Fallback news data expired for keywords '{keywords}'")
            return None
        
        articles = self._fallback_news[keywords]
        return articles[-limit:] if articles else None
    
    def cleanup_expired_data(self):
        """Clean up expired fallback data."""
        current_time = datetime.utcnow()
        expired_keys = []
        
        for key, last_updated in self._last_updated.items():
            if (current_time - last_updated) > timedelta(hours=self._fallback_ttl_hours):
                expired_keys.append(key)
        
        for key in expired_keys:
            if key.startswith("news_"):
                keywords = key[5:]  # Remove "news_" prefix
                if keywords in self._fallback_news:
                    del self._fallback_news[keywords]
            else:
                if key in self._fallback_quotes:
                    del self._fallback_quotes[key]
            del self._last_updated[key]
        
        if expired_keys:
            self.logger.info(f"Cleaned up {len(expired_keys)} expired fallback data entries")


class GracefulDegradationManager(LoggerMixin):
    """Manages graceful degradation strategies."""
    
    def __init__(self):
        self.current_level = DegradationLevels.FULL
        self.fallback_manager = FallbackDataManager()
        self._service_health: Dict[str, bool] = {}
        self._last_health_check: Dict[str, datetime] = {}
        self._health_check_interval_minutes = 5
    
    def update_service_health(self, service_name: str, is_healthy: bool):
        """Update the health status of a service."""
        self._service_health[service_name] = is_healthy
        self._last_health_check[service_name] = datetime.utcnow()
        
        # Adjust degradation level based on overall health
        self._adjust_degradation_level()
        
        self.logger.info(f"Service health updated: {service_name} = {'healthy' if is_healthy else 'unhealthy'}")
    
    def get_service_health(self, service_name: str) -> Optional[bool]:
        """Get the health status of a service."""
        return self._service_health.get(service_name)
    
    def is_health_check_needed(self, service_name: str) -> bool:
        """Check if a health check is needed for a service."""
        last_check = self._last_health_check.get(service_name)
        if not last_check:
            return True
        
        return (datetime.utcnow() - last_check) > timedelta(minutes=self._health_check_interval_minutes)
    
    def _adjust_degradation_level(self):
        """Adjust degradation level based on service health."""
        if not self._service_health:
            return
        
        healthy_services = sum(1 for is_healthy in self._service_health.values() if is_healthy)
        total_services = len(self._service_health)
        
        if healthy_services == total_services:
            new_level = DegradationLevels.FULL
        elif healthy_services >= total_services * 0.75:
            new_level = DegradationLevels.PARTIAL
        elif healthy_services >= total_services * 0.25:
            new_level = DegradationLevels.MINIMAL
        else:
            new_level = DegradationLevels.OFFLINE
        
        if new_level.level != self.current_level.level:
            old_level = self.current_level.name
            self.current_level = new_level
            self.logger.warning(f"Degradation level changed: {old_level} -> {new_level.name}")
    
    def get_degradation_status(self) -> Dict[str, Any]:
        """Get current degradation status."""
        return {
            "level": self.current_level.name,
            "level_number": self.current_level.level,
            "description": self.current_level.description,
            "service_health": self._service_health.copy(),
            "fallback_available": {
                "quotes": len(self.fallback_manager._fallback_quotes),
                "news": len(self.fallback_manager._fallback_news)
            }
        }


class DegradedMarketDataService(LoggerMixin):
    """Market data service with graceful degradation."""
    
    def __init__(self, degradation_manager: GracefulDegradationManager):
        self.degradation_manager = degradation_manager
        self.coingecko_client = None
        self.yahoo_client = None
    
    def get_market_data(self, symbol: str, asset_type: str, days: int = 30) -> List[QuoteBarDto]:
        """Get market data with graceful degradation."""
        try:
            # Try to get fresh data first
            fresh_data = self._get_fresh_market_data(symbol, asset_type, days)
            if fresh_data:
                # Store as fallback for future use
                self.degradation_manager.fallback_manager.store_quotes_fallback(symbol, fresh_data)
                return fresh_data
        except Exception as e:
            self.logger.error(f"Failed to get fresh market data for {symbol}: {e}")
            self.degradation_manager.update_service_health(
                "coingecko" if asset_type == "crypto" else "yahoo_finance", 
                False
            )
        
        # Fallback to cached data
        fallback_data = self.degradation_manager.fallback_manager.get_quotes_fallback(symbol, days)
        if fallback_data:
            self.logger.info(f"Using fallback data for {symbol}")
            return fallback_data
        
        # Generate synthetic data as last resort
        if self.degradation_manager.current_level.level >= DegradationLevels.MINIMAL.level:
            synthetic_data = self._generate_synthetic_data(symbol, days)
            self.logger.warning(f"Using synthetic data for {symbol}")
            return synthetic_data
        
        # No data available
        self.logger.error(f"No market data available for {symbol}")
        return []
    
    def _get_fresh_market_data(self, symbol: str, asset_type: str, days: int) -> Optional[List[QuoteBarDto]]:
        """Get fresh market data from external APIs."""
        if asset_type == "crypto" and self.coingecko_client:
            try:
                data = self.coingecko_client.get_price_history(symbol.lower(), days)
                return self._convert_coingecko_data(data)
            except Exception as e:
                self.logger.error(f"CoinGecko API failed for {symbol}: {e}")
                raise
        elif self.yahoo_client:
            try:
                ticker = f"{symbol}-USD" if asset_type == "crypto" else symbol
                data = self.yahoo_client.download_history(ticker, f"{days}d")
                return self._convert_yahoo_data(data)
            except Exception as e:
                self.logger.error(f"Yahoo Finance API failed for {symbol}: {e}")
                raise
        
        return None
    
    def _convert_coingecko_data(self, data: Dict) -> List[QuoteBarDto]:
        """Convert CoinGecko data to QuoteBarDto."""
        quotes = []
        for timestamp, price in data.get("prices", []):
            quotes.append(QuoteBarDto(
                ts=datetime.fromtimestamp(timestamp / 1000),
                close=float(price),
                open=None,
                high=None,
                low=None,
                volume=None
            ))
        return quotes
    
    def _convert_yahoo_data(self, data: pd.DataFrame) -> List[QuoteBarDto]:
        """Convert Yahoo Finance data to QuoteBarDto."""
        quotes = []
        for timestamp, row in data.iterrows():
            quotes.append(QuoteBarDto(
                ts=timestamp.to_pydatetime(),
                close=float(row['Close']),
                open=float(row['Open']) if pd.notna(row['Open']) else None,
                high=float(row['High']) if pd.notna(row['High']) else None,
                low=float(row['Low']) if pd.notna(row['Low']) else None,
                volume=float(row['Volume']) if pd.notna(row['Volume']) else None
            ))
        return quotes
    
    def _generate_synthetic_data(self, symbol: str, days: int) -> List[QuoteBarDto]:
        """Generate synthetic market data as last resort."""
        base_date = datetime.utcnow() - timedelta(days=days)
        base_price = 50000.0 if symbol.upper() == "BTC" else 100.0
        
        quotes = []
        for i in range(days):
            date = base_date + timedelta(days=i)
            # Simple random walk
            price_change = (hash(f"{symbol}_{i}") % 1000 - 500) / 10000  # -5% to +5%
            price = base_price * (1 + price_change * i * 0.1)
            
            quotes.append(QuoteBarDto(
                ts=date,
                close=price,
                open=price * 0.99,
                high=price * 1.02,
                low=price * 0.98,
                volume=1000000
            ))
        
        return quotes


class DegradedNewsService(LoggerMixin):
    """News service with graceful degradation."""
    
    def __init__(self, degradation_manager: GracefulDegradationManager):
        self.degradation_manager = degradation_manager
        self.news_client = None
        self.finnhub_client = None
    
    def get_news(self, keywords: str, limit: int = 50) -> List[NewsArticleRawDto]:
        """Get news with graceful degradation."""
        try:
            # Try to get fresh news first
            fresh_news = self._get_fresh_news(keywords, limit)
            if fresh_news:
                # Store as fallback for future use
                self.degradation_manager.fallback_manager.store_news_fallback(keywords, fresh_news)
                return fresh_news
        except Exception as e:
            self.logger.error(f"Failed to get fresh news for keywords '{keywords}': {e}")
            self.degradation_manager.update_service_health("newsapi", False)
        
        # Fallback to cached news
        fallback_news = self.degradation_manager.fallback_manager.get_news_fallback(keywords, limit)
        if fallback_news:
            self.logger.info(f"Using fallback news for keywords '{keywords}'")
            return fallback_news
        
        # Generate placeholder news as last resort
        if self.degradation_manager.current_level.level >= DegradationLevels.MINIMAL.level:
            placeholder_news = self._generate_placeholder_news(keywords, min(limit, 5))
            self.logger.warning(f"Using placeholder news for keywords '{keywords}'")
            return placeholder_news
        
        # No news available
        self.logger.error(f"No news available for keywords '{keywords}'")
        return []
    
    def _get_fresh_news(self, keywords: str, limit: int) -> Optional[List[NewsArticleRawDto]]:
        """Get fresh news from external APIs."""
        if self.news_client:
            try:
                data = self.news_client.get_everything(keywords, limit)
                return self._convert_newsapi_data(data)
            except Exception as e:
                self.logger.error(f"NewsAPI failed for keywords '{keywords}': {e}")
                raise
        
        return None
    
    def _convert_newsapi_data(self, data: Dict) -> List[NewsArticleRawDto]:
        """Convert NewsAPI data to NewsArticleRawDto."""
        articles = []
        for article in data.get("articles", []):
            published_at = datetime.fromisoformat(article["publishedAt"].replace("Z", "+00:00"))
            articles.append(NewsArticleRawDto(
                published_at=published_at,
                title=article["title"],
                url=article["url"],
                source=article["source"]["name"],
                snippet=article["description"]
            ))
        return articles
    
    def _generate_placeholder_news(self, keywords: str, count: int) -> List[NewsArticleRawDto]:
        """Generate placeholder news articles."""
        articles = []
        base_date = datetime.utcnow()
        
        for i in range(count):
            published_at = base_date - timedelta(hours=i)
            articles.append(NewsArticleRawDto(
                published_at=published_at,
                title=f"Market Update for {keywords.title()} - {published_at.strftime('%Y-%m-%d')}",
                url=None,
                source="System Generated",
                snippet=f"This is a placeholder news article for {keywords} due to service unavailability."
            ))
        
        return articles


# Global degradation manager instance
degradation_manager = GracefulDegradationManager()
