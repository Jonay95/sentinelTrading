"""
Redis caching layer for Sentinel Trading application.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional, Union, List, Dict
import redis
from redis.exceptions import RedisError, ConnectionError
import pickle
import hashlib

from app.infrastructure.logging_config import LoggerMixin

logger = logging.getLogger(__name__)


class CacheManager(LoggerMixin):
    """Redis cache manager with serialization and TTL management."""
    
    def __init__(self, redis_url: str = None, default_ttl: int = 3600):
        """
        Initialize cache manager.
        
        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0)
            default_ttl: Default time-to-live in seconds
        """
        self.default_ttl = default_ttl
        self.redis_client = None
        self._connected = False
        
        if redis_url:
            self.connect(redis_url)
    
    def connect(self, redis_url: str) -> bool:
        """Connect to Redis server."""
        try:
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=False,  # Handle binary data ourselves
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            self.redis_client.ping()
            self._connected = True
            
            self.logger.info(f"Connected to Redis: {redis_url}")
            return True
            
        except (ConnectionError, RedisError) as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
            return False
    
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        if not self._connected or not self.redis_client:
            return False
        
        try:
            self.redis_client.ping()
            return True
        except RedisError:
            self._connected = False
            return False
    
    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage."""
        try:
            return pickle.dumps(value)
        except (pickle.PickleError, TypeError) as e:
            self.logger.error(f"Failed to serialize value: {e}")
            # Fallback to JSON for simple types
            try:
                return json.dumps(value).encode('utf-8')
            except (TypeError, ValueError):
                return str(value).encode('utf-8')
    
    def _deserialize(self, value: bytes) -> Any:
        """Deserialize value from storage."""
        try:
            return pickle.loads(value)
        except (pickle.PickleError, TypeError):
            # Fallback to JSON
            try:
                return json.loads(value.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return value.decode('utf-8', errors='ignore')
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set a value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
        
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            self.logger.warning("Redis not connected, cache set failed")
            return False
        
        try:
            serialized_value = self._serialize(value)
            actual_ttl = ttl if ttl is not None else self.default_ttl
            
            result = self.redis_client.setex(key, actual_ttl, serialized_value)
            
            if result:
                self.logger.debug(f"Cached key: {key} (TTL: {actual_ttl}s)")
            
            return bool(result)
            
        except RedisError as e:
            self.logger.error(f"Failed to set cache key {key}: {e}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from cache.
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None if not found
        """
        if not self.is_connected():
            self.logger.warning("Redis not connected, cache get failed")
            return None
        
        try:
            value = self.redis_client.get(key)
            
            if value is None:
                self.logger.debug(f"Cache miss: {key}")
                return None
            
            deserialized_value = self._deserialize(value)
            self.logger.debug(f"Cache hit: {key}")
            
            return deserialized_value
            
        except RedisError as e:
            self.logger.error(f"Failed to get cache key {key}: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        if not self.is_connected():
            return False
        
        try:
            result = self.redis_client.delete(key)
            if result:
                self.logger.debug(f"Deleted cache key: {key}")
            return bool(result)
        except RedisError as e:
            self.logger.error(f"Failed to delete cache key {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching a pattern."""
        if not self.is_connected():
            return 0
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                count = self.redis_client.delete(*keys)
                self.logger.info(f"Deleted {count} keys matching pattern: {pattern}")
                return count
            return 0
        except RedisError as e:
            self.logger.error(f"Failed to delete pattern {pattern}: {e}")
            return 0
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.is_connected():
            return False
        
        try:
            return bool(self.redis_client.exists(key))
        except RedisError as e:
            self.logger.error(f"Failed to check existence of key {key}: {e}")
            return False
    
    def get_ttl(self, key: str) -> int:
        """Get remaining TTL for a key."""
        if not self.is_connected():
            return -1
        
        try:
            return self.redis_client.ttl(key)
        except RedisError as e:
            self.logger.error(f"Failed to get TTL for key {key}: {e}")
            return -1
    
    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a numeric value."""
        if not self.is_connected():
            return None
        
        try:
            return self.redis_client.incrby(key, amount)
        except RedisError as e:
            self.logger.error(f"Failed to increment key {key}: {e}")
            return None
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get Redis cache information."""
        if not self.is_connected():
            return {"connected": False}
        
        try:
            info = self.redis_client.info()
            return {
                "connected": True,
                "used_memory": info.get("used_memory_human"),
                "used_memory_peak": info.get("used_memory_peak_human"),
                "connected_clients": info.get("connected_clients"),
                "total_commands_processed": info.get("total_commands_processed"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(info),
            }
        except RedisError as e:
            self.logger.error(f"Failed to get cache info: {e}")
            return {"connected": False, "error": str(e)}
    
    def _calculate_hit_rate(self, info: Dict) -> float:
        """Calculate cache hit rate."""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        
        if total == 0:
            return 0.0
        
        return round((hits / total) * 100, 2)


class CacheKeyManager:
    """Manages cache key generation and organization."""
    
    PREFIX = "sentinel_trading"
    
    @classmethod
    def asset_key(cls, asset_id: int) -> str:
        """Generate cache key for asset data."""
        return f"{cls.PREFIX}:asset:{asset_id}"
    
    @classmethod
    def asset_quotes_key(cls, asset_id: int, days: int = 30) -> str:
        """Generate cache key for asset quotes."""
        return f"{cls.PREFIX}:quotes:{asset_id}:{days}"
    
    @classmethod
    def predictions_key(cls, asset_id: int) -> str:
        """Generate cache key for predictions."""
        return f"{cls.PREFIX}:predictions:{asset_id}"
    
    @classmethod
    def dashboard_key(cls, user_id: Optional[str] = None) -> str:
        """Generate cache key for dashboard data."""
        user_suffix = f":{user_id}" if user_id else ""
        return f"{cls.PREFIX}:dashboard{user_suffix}"
    
    @classmethod
    def news_key(cls, keywords: str, limit: int = 50) -> str:
        """Generate cache key for news."""
        # Hash keywords to avoid long keys
        keywords_hash = hashlib.md5(keywords.encode()).hexdigest()
        return f"{cls.PREFIX}:news:{keywords_hash}:{limit}"
    
    @classmethod
    def metrics_key(cls, metric_type: str, params: Dict = None) -> str:
        """Generate cache key for metrics."""
        if params:
            # Sort params and create hash for consistent keys
            sorted_params = json.dumps(params, sort_keys=True)
            params_hash = hashlib.md5(sorted_params.encode()).hexdigest()
            return f"{cls.PREFIX}:metrics:{metric_type}:{params_hash}"
        return f"{cls.PREFIX}:metrics:{metric_type}"
    
    @classmethod
    def api_response_key(cls, endpoint: str, params: Dict = None) -> str:
        """Generate cache key for API responses."""
        if params:
            sorted_params = json.dumps(params, sort_keys=True)
            params_hash = hashlib.md5(sorted_params.encode()).hexdigest()
            return f"{cls.PREFIX}:api:{endpoint}:{params_hash}"
        return f"{cls.PREFIX}:api:{endpoint}"
    
    @classmethod
    def session_key(cls, session_id: str) -> str:
        """Generate cache key for session data."""
        return f"{cls.PREFIX}:session:{session_id}"


class CacheDecorator:
    """Decorator for caching function results."""
    
    def __init__(self, cache_manager: CacheManager, ttl: int = 3600, 
                 key_generator: callable = None):
        self.cache_manager = cache_manager
        self.ttl = ttl
        self.key_generator = key_generator or self._default_key_generator
    
    def _default_key_generator(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Generate default cache key."""
        key_data = {
            "func": func_name,
            "args": args,
            "kwargs": sorted(kwargs.items())
        }
        key_hash = hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
        return f"decorator:{func_name}:{key_hash}"
    
    def __call__(self, func):
        """Decorator implementation."""
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = self.key_generator(func.__name__, args, kwargs)
            
            # Try to get from cache
            cached_result = self.cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            self.cache_manager.set(cache_key, result, self.ttl)
            
            return result
        
        return wrapper


# Global cache instance
cache_manager = CacheManager()

def init_cache(redis_url: str, default_ttl: int = 3600) -> CacheManager:
    """Initialize global cache manager."""
    global cache_manager
    cache_manager = CacheManager(redis_url, default_ttl)
    return cache_manager

def get_cache() -> CacheManager:
    """Get global cache manager."""
    return cache_manager

# Cache decorators for common use cases
def cache_asset_data(ttl: int = 1800):  # 30 minutes
    """Decorator for caching asset data."""
    return CacheDecorator(cache_manager, ttl, lambda f, a, k: CacheKeyManager.asset_key(a[0] if a else 0))

def cache_quotes(ttl: int = 300):  # 5 minutes
    """Decorator for caching quote data."""
    return CacheDecorator(cache_manager, ttl, lambda f, a, k: CacheKeyManager.asset_quotes_key(a[0] if a else 0, k.get('days', 30)))

def cache_predictions(ttl: int = 600):  # 10 minutes
    """Decorator for caching prediction data."""
    return CacheDecorator(cache_manager, ttl, lambda f, a, k: CacheKeyManager.predictions_key(a[0] if a else 0))

def cache_news(ttl: int = 900):  # 15 minutes
    """Decorator for caching news data."""
    return CacheDecorator(cache_manager, ttl, lambda f, a, k: CacheKeyManager.news_key(k.get('keywords', ''), k.get('limit', 50)))

def cache_dashboard(ttl: int = 300):  # 5 minutes
    """Decorator for caching dashboard data."""
    return CacheDecorator(cache_manager, ttl, lambda f, a, k: CacheKeyManager.dashboard_key(k.get('user_id')))
