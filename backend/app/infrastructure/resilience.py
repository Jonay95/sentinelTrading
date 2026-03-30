"""
Resilience patterns for external API calls: circuit breakers and retry mechanisms.
"""

import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional
from circuitbreaker import circuit
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class CircuitBreakerManager:
    """Manages circuit breakers for different external services."""
    
    def __init__(self):
        self._breakers: Dict[str, Any] = {}
    
    def get_breaker(self, service_name: str, failure_threshold: int = 5, 
                   recovery_timeout: int = 60, expected_exception: type = Exception):
        """Get or create a circuit breaker for a specific service."""
        if service_name not in self._breakers:
            self._breakers[service_name] = circuit(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=expected_exception
            )
        return self._breakers[service_name]
    
    def register_service(self, service_name: str, failure_threshold: int = 5,
                         recovery_timeout: int = 60, expected_exception: type = Exception):
        """Register a new service with circuit breaker protection."""
        self._breakers[service_name] = self.get_breaker(
            service_name, failure_threshold, recovery_timeout, expected_exception
        )
    
    def get_service_status(self, service_name: str) -> str:
        """Get the current status of a circuit breaker."""
        if service_name not in self._breakers:
            return "UNKNOWN"
        
        breaker = self._breakers[service_name]
        if getattr(breaker, 'is_open', lambda: False)():
            return "OPEN"
        elif getattr(breaker, 'is_half_open', lambda: False)():
            return "HALF_OPEN"
        else:
            return "CLOSED"


# Global circuit breaker manager
circuit_breaker_manager = CircuitBreakerManager()

# Register default services
circuit_breaker_manager.register_service("coingecko", failure_threshold=5, recovery_timeout=60)
circuit_breaker_manager.register_service("yahoo_finance", failure_threshold=5, recovery_timeout=60)
circuit_breaker_manager.register_service("newsapi", failure_threshold=3, recovery_timeout=120)
circuit_breaker_manager.register_service("finnhub", failure_threshold=3, recovery_timeout=120)


def with_circuit_breaker(service_name: str, fallback_value: Any = None):
    """Decorator to apply circuit breaker protection to a function."""
    def decorator(func: Callable) -> Callable:
        breaker = circuit_breaker_manager.get_breaker(service_name)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return breaker(func)(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Circuit breaker open for {service_name}: {e}")
                if fallback_value is not None:
                    return fallback_value
                raise
        
        return wrapper
    return decorator


def with_retry(max_attempts: int = 3, min_wait: float = 1.0, max_wait: float = 10.0,
               retry_exceptions: tuple = (Exception,)):
    """Decorator to apply retry mechanism with exponential backoff."""
    def decorator(func: Callable) -> Callable:
        return retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type(retry_exceptions),
            before_sleep=lambda retry_state: logger.warning(
                f"Retry attempt {retry_state.attempt_number} for {func.__name__} "
                f"after {retry_state.seconds_since_start:.2f}s"
            )
        )(func)
    return decorator


def with_resilience(service_name: str, max_attempts: int = 3, 
                   fallback_value: Any = None, retry_exceptions: tuple = (Exception,)):
    """Combined decorator for both circuit breaker and retry."""
    def decorator(func: Callable) -> Callable:
        # Apply retry first, then circuit breaker
        retry_func = with_retry(max_attempts=max_attempts, retry_exceptions=retry_exceptions)(func)
        return with_circuit_breaker(service_name, fallback_value)(retry_func)
    return decorator


class ResilientAPIClient:
    """Base class for resilient API clients."""
    
    def __init__(self, service_name: str, max_attempts: int = 3):
        self.service_name = service_name
        self.max_attempts = max_attempts
        self.logger = logging.getLogger(f"{__name__}.{service_name}")
    
    def _make_resilient_call(self, func: Callable, fallback_value: Any = None, *args, **kwargs):
        """Make a resilient API call with circuit breaker and retry."""
        try:
            return with_resilience(
                service_name=self.service_name,
                max_attempts=self.max_attempts,
                fallback_value=fallback_value
            )(func)(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"API call failed for {self.service_name}: {e}")
            if fallback_value is not None:
                return fallback_value
            raise
    
    def get_status(self) -> str:
        """Get the current circuit breaker status."""
        return circuit_breaker_manager.get_service_status(self.service_name)


class ResilientCoinGeckoClient(ResilientAPIClient):
    """Resilient CoinGecko API client."""
    
    def __init__(self):
        super().__init__("coingecko", max_attempts=3)
    
    def get_price_history(self, coin_id: str, days: int, vs_currency: str = "usd"):
        """Get price history with resilience."""
        def _get_history():
            import requests
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
            params = {
                "vs_currency": vs_currency,
                "days": days
            }
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        
        return self._make_resilient_call(
            _get_history,
            fallback_value={"prices": [], "market_caps": [], "total_volumes": []}
        )
    
    def get_simple_price(self, coin_ids: str, vs_currencies: str = "usd"):
        """Get simple price with resilience."""
        def _get_simple_price():
            import requests
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": coin_ids,
                "vs_currencies": vs_currencies
            }
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        
        return self._make_resilient_call(
            _get_simple_price,
            fallback_value={}
        )


class ResilientYahooFinanceClient(ResilientAPIClient):
    """Resilient Yahoo Finance API client."""
    
    def __init__(self):
        super().__init__("yahoo_finance", max_attempts=3)
    
    def download_history(self, ticker: str, period: str = "1y"):
        """Download historical data with resilience."""
        def _download():
            import yfinance as yf
            data = yf.download(ticker, period=period, timeout=30)
            if data.empty:
                raise Exception(f"No data returned for ticker {ticker}")
            return data
        
        return self._make_resilient_call(
            _download,
            fallback_value=None
        )


class ResilientNewsAPIClient(ResilientAPIClient):
    """Resilient NewsAPI client."""
    
    def __init__(self, api_key: str):
        super().__init__("newsapi", max_attempts=2)
        self.api_key = api_key
    
    def get_everything(self, q: str, page_size: int = 10):
        """Get news articles with resilience."""
        def _get_news():
            import requests
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": q,
                "apiKey": self.api_key,
                "pageSize": page_size,
                "sortBy": "publishedAt"
            }
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        
        return self._make_resilient_call(
            _get_news,
            fallback_value={"status": "ok", "totalResults": 0, "articles": []}
        )


class ResilientFinnhubClient(ResilientAPIClient):
    """Resilient Finnhub API client."""
    
    def __init__(self, api_key: str):
        super().__init__("finnhub", max_attempts=2)
        self.api_key = api_key
    
    def get_company_news(self, symbol: str, from_date: str, to_date: str):
        """Get company news with resilience."""
        def _get_news():
            import requests
            url = "https://finnhub.io/api/v1/company-news"
            params = {
                "symbol": symbol,
                "from": from_date,
                "to": to_date,
                "token": self.api_key
            }
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        
        return self._make_resilient_call(
            _get_news,
            fallback_value=[]
        )


def get_circuit_breaker_status() -> Dict[str, str]:
    """Get status of all circuit breakers."""
    status = {}
    for service_name in ["coingecko", "yahoo_finance", "newsapi", "finnhub"]:
        status[service_name] = circuit_breaker_manager.get_service_status(service_name)
    return status


def reset_circuit_breaker(service_name: str):
    """Reset a specific circuit breaker (for testing/admin purposes)."""
    if service_name in circuit_breaker_manager._breakers:
        breaker = circuit_breaker_manager._breakers[service_name]
        if hasattr(breaker, '_state'):
            breaker._state.closed = True
            breaker._state.failure_count = 0
        logger.info(f"Circuit breaker reset for {service_name}")
