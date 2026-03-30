"""
API Gateway implementation for Sentinel Trading microservices.
"""

import logging
import asyncio
import json
import httpx
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
from fastapi import FastAPI, Request, Response, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import jwt
import redis
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import time
import uuid

from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache
from app.infrastructure.metrics import get_metrics
from app.infrastructure.notifications import get_notification_manager

logger = logging.getLogger(__name__)


class ServiceType(Enum):
    """Types of microservices."""
    PREDICTION = "prediction"
    TRADING = "trading"
    RISK = "risk"
    DATA = "data"
    NOTIFICATION = "notification"
    AUTH = "auth"
    ANALYTICS = "analytics"


class RouteType(Enum):
    """Route types."""
    PROXY = "proxy"
    AGGREGATE = "aggregate"
    TRANSFORM = "transform"
    CACHE = "cache"
    AUTHENTICATE = "authenticate"
    RATE_LIMIT = "rate_limit"


@dataclass
class ServiceEndpoint:
    """Service endpoint configuration."""
    service_name: str
    service_type: ServiceType
    base_url: str
    health_endpoint: str
    timeout: int
    retry_count: int
    circuit_breaker_threshold: int
    circuit_breaker_timeout: int
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['service_type'] = self.service_type.value
        return result


@dataclass
class RouteConfig:
    """Route configuration."""
    path: str
    method: str
    service_endpoint: str
    route_type: RouteType
    auth_required: bool = True
    rate_limit: Optional[int] = None
    cache_ttl: Optional[int] = None
    transform_function: Optional[str] = None
    aggregation_services: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['route_type'] = self.route_type.value
        return result


@dataclass
class CircuitBreakerState:
    """Circuit breaker state."""
    service_name: str
    is_open: bool = False
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    success_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if self.last_failure_time:
            result['last_failure_time'] = self.last_failure_time.isoformat()
        return result


class CircuitBreaker(LoggerMixin):
    """Circuit breaker implementation."""
    
    def __init__(self, service_name: str, threshold: int = 5, timeout: int = 60):
        self.service_name = service_name
        self.threshold = threshold
        self.timeout = timeout
        self.state = CircuitBreakerState(service_name=service_name)
        self.lock = asyncio.Lock()
    
    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        async with self.lock:
            # Check if circuit is open
            if self.state.is_open:
                if self._should_attempt_reset():
                    self.state.is_open = False
                    self.state.success_count = 0
                    self.logger.info(f"Circuit breaker for {self.service_name} reset")
                else:
                    raise Exception(f"Circuit breaker for {self.service_name} is open")
            
            try:
                result = await func(*args, **kwargs)
                
                # Success - reset failure count
                self.state.failure_count = 0
                self.state.success_count += 1
                
                # Close circuit if we have enough successes
                if self.state.success_count >= 3:
                    self.state.is_open = False
                
                return result
                
            except Exception as e:
                self.state.failure_count += 1
                self.state.last_failure_time = datetime.utcnow()
                
                # Open circuit if threshold reached
                if self.state.failure_count >= self.threshold:
                    self.state.is_open = True
                    self.logger.warning(f"Circuit breaker for {self.service_name} opened after {self.state.failure_count} failures")
                
                raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset."""
        if not self.state.last_failure_time:
            return True
        
        return (datetime.utcnow() - self.state.last_failure_time).total_seconds() >= self.timeout
    
    def get_state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        return self.state


class RateLimiter(LoggerMixin):
    """Rate limiter implementation."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.metrics = get_metrics()
    
    async def is_allowed(self, key: str, limit: int, window: int = 60) -> bool:
        """Check if request is allowed based on rate limit."""
        try:
            current_time = int(time.time())
            window_start = current_time - window
            
            # Remove expired entries
            self.redis_client.zremrangebyscore(key, 0, window_start)
            
            # Check current count
            current_count = self.redis_client.zcard(key)
            
            if current_count >= limit:
                return False
            
            # Add current request
            self.redis_client.zadd(key, {str(current_time): current_time})
            self.redis_client.expire(key, window)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking rate limit: {e}")
            return True  # Allow on error


class APIGateway(LoggerMixin):
    """Main API Gateway implementation."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.notification_manager = get_notification_manager()
        
        # Service registry
        self.services: Dict[str, ServiceEndpoint] = {}
        
        # Route registry
        self.routes: Dict[str, RouteConfig] = {}
        
        # Circuit breakers
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Rate limiter
        self.redis_client = redis.Redis(host='localhost', port=6379, db=0)
        self.rate_limiter = RateLimiter(self.redis_client)
        
        # HTTP client
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Prometheus metrics
        self.request_count = Counter('api_gateway_requests_total', ['method', 'path', 'status'])
        self.request_duration = Histogram('api_gateway_request_duration_seconds', ['method', 'path'])
        self.active_connections = Gauge('api_gateway_active_connections')
        
        # Initialize default services
        self._initialize_default_services()
        self._initialize_default_routes()
    
    def _initialize_default_services(self):
        """Initialize default service endpoints."""
        services = [
            ServiceEndpoint(
                service_name="prediction_service",
                service_type=ServiceType.PREDICTION,
                base_url="http://localhost:8001",
                health_endpoint="/health",
                timeout=30,
                retry_count=3,
                circuit_breaker_threshold=5,
                circuit_breaker_timeout=60
            ),
            ServiceEndpoint(
                service_name="trading_service",
                service_type=ServiceType.TRADING,
                base_url="http://localhost:8002",
                health_endpoint="/health",
                timeout=15,
                retry_count=2,
                circuit_breaker_threshold=3,
                circuit_breaker_timeout=30
            ),
            ServiceEndpoint(
                service_name="risk_service",
                service_type=ServiceType.RISK,
                base_url="http://localhost:8003",
                health_endpoint="/health",
                timeout=20,
                retry_count=3,
                circuit_breaker_threshold=5,
                circuit_breaker_timeout=60
            ),
            ServiceEndpoint(
                service_name="data_service",
                service_type=ServiceType.DATA,
                base_url="http://localhost:8004",
                health_endpoint="/health",
                timeout=10,
                retry_count=2,
                circuit_breaker_threshold=3,
                circuit_breaker_timeout=30
            )
        ]
        
        for service in services:
            self.services[service.service_name] = service
            self.circuit_breakers[service.service_name] = CircuitBreaker(
                service.service_name,
                service.circuit_breaker_threshold,
                service.circuit_breaker_timeout
            )
    
    def _initialize_default_routes(self):
        """Initialize default routes."""
        routes = [
            # Prediction routes
            RouteConfig(
                path="/predictions/batch",
                method="POST",
                service_endpoint="prediction_service",
                route_type=RouteType.PROXY,
                auth_required=True,
                rate_limit=100
            ),
            RouteConfig(
                path="/predictions/realtime",
                method="POST",
                service_endpoint="prediction_service",
                route_type=RouteType.PROXY,
                auth_required=True,
                rate_limit=1000
            ),
            RouteConfig(
                path="/predictions/{request_id}",
                method="GET",
                service_endpoint="prediction_service",
                route_type=RouteType.PROXY,
                auth_required=True,
                cache_ttl=300
            ),
            
            # Trading routes
            RouteConfig(
                path="/trades/execute",
                method="POST",
                service_endpoint="trading_service",
                route_type=RouteType.PROXY,
                auth_required=True,
                rate_limit=50
            ),
            RouteConfig(
                path="/portfolio",
                method="GET",
                service_endpoint="trading_service",
                route_type=RouteType.PROXY,
                auth_required=True,
                cache_ttl=60
            ),
            
            # Risk routes
            RouteConfig(
                path="/risk/assess",
                method="POST",
                service_endpoint="risk_service",
                route_type=RouteType.PROXY,
                auth_required=True,
                rate_limit=100
            ),
            RouteConfig(
                path="/risk/position-sizing",
                method="POST",
                service_endpoint="risk_service",
                route_type=RouteType.PROXY,
                auth_required=True,
                rate_limit=50
            ),
            
            # Data routes
            RouteConfig(
                path="/data/market/{symbol}",
                method="GET",
                service_endpoint="data_service",
                route_type=RouteType.PROXY,
                auth_required=True,
                cache_ttl=60
            ),
            RouteConfig(
                path="/data/quotes",
                method="GET",
                service_endpoint="data_service",
                route_type=RouteType.PROXY,
                auth_required=True,
                cache_ttl=30
            ),
            
            # Aggregated routes
            RouteConfig(
                path="/dashboard",
                method="GET",
                service_endpoint="",
                route_type=RouteType.AGGREGATE,
                auth_required=True,
                cache_ttl=300,
                aggregation_services=["trading_service", "risk_service", "data_service"]
            )
        ]
        
        for route in routes:
            route_key = f"{route.method}:{route.path}"
            self.routes[route_key] = route
    
    async def route_request(self, request: Request) -> Response:
        """Route incoming request to appropriate service."""
        start_time = time.time()
        
        try:
            method = request.method
            path = request.url.path
            route_key = f"{method}:{path}"
            
            # Find matching route
            route = self._find_matching_route(method, path)
            if not route:
                raise HTTPException(status_code=404, detail="Route not found")
            
            # Check authentication
            if route.auth_required:
                await self._authenticate_request(request)
            
            # Check rate limiting
            if route.rate_limit:
                client_id = self._get_client_id(request)
                if not await self.rate_limiter.is_allowed(client_id, route.rate_limit):
                    raise HTTPException(status_code=429, detail="Rate limit exceeded")
            
            # Check cache
            if route.cache_ttl and method == "GET":
                cached_response = await self._get_cached_response(request, route.cache_ttl)
                if cached_response:
                    return cached_response
            
            # Route based on type
            if route.route_type == RouteType.PROXY:
                response = await self._proxy_request(request, route)
            elif route.route_type == RouteType.AGGREGATE:
                response = await self._aggregate_request(request, route)
            elif route.route_type == RouteType.TRANSFORM:
                response = await self._transform_request(request, route)
            else:
                raise HTTPException(status_code=500, detail="Unsupported route type")
            
            # Cache response if applicable
            if route.cache_ttl and method == "GET" and response.status_code == 200:
                await self._cache_response(request, response, route.cache_ttl)
            
            # Record metrics
            duration = time.time() - start_time
            self.request_count.labels(method=method, path=path, status=str(response.status_code)).inc()
            self.request_duration.labels(method=method, path=path).observe(duration)
            
            return response
            
        except HTTPException:
            duration = time.time() - start_time
            self.request_count.labels(method=request.method, path=request.url.path, status="4xx").inc()
            self.request_duration.labels(method=request.method, path=request.url.path).observe(duration)
            raise
        except Exception as e:
            duration = time.time() - start_time
            self.request_count.labels(method=request.method, path=request.url.path, status="5xx").inc()
            self.request_duration.labels(method=request.method, path=request.url.path).observe(duration)
            
            self.logger.error(f"Error routing request: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    def _find_matching_route(self, method: str, path: str) -> Optional[RouteConfig]:
        """Find matching route for method and path."""
        # Exact match first
        route_key = f"{method}:{path}"
        if route_key in self.routes:
            return self.routes[route_key]
        
        # Pattern matching (simple implementation)
        for route_key, route in self.routes.items():
            if route_key.startswith(f"{method}:"):
                route_path = route_key.split(":", 1)[1]
                if self._path_matches(path, route_path):
                    return route
        
        return None
    
    def _path_matches(self, actual_path: str, route_path: str) -> bool:
        """Check if actual path matches route path (simple pattern matching)."""
        # Split paths
        actual_parts = actual_path.strip("/").split("/")
        route_parts = route_path.strip("/").split("/")
        
        # Must have same number of parts
        if len(actual_parts) != len(route_parts):
            return False
        
        # Check each part
        for actual, route in zip(actual_parts, route_parts):
            # Route parameters start with { or end with }
            if not (route.startswith("{") or route.endswith("}")):
                if actual != route:
                    return False
        
        return True
    
    async def _authenticate_request(self, request: Request):
        """Authenticate incoming request."""
        try:
            # Get authorization header
            auth_header = request.headers.get("Authorization")
            
            if not auth_header:
                raise HTTPException(status_code=401, detail="Authorization header missing")
            
            # Extract token
            try:
                scheme, token = auth_header.split()
                if scheme.lower() != "bearer":
                    raise HTTPException(status_code=401, detail="Invalid authentication scheme")
            except ValueError:
                raise HTTPException(status_code=401, detail="Invalid authorization header format")
            
            # Verify JWT token (simplified)
            try:
                payload = jwt.decode(token, "your-secret-key", algorithms=["HS256"])
                request.state.user = payload
            except jwt.ExpiredSignatureError:
                raise HTTPException(status_code=401, detail="Token expired")
            except jwt.InvalidTokenError:
                raise HTTPException(status_code=401, detail="Invalid token")
                
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Authentication error: {e}")
            raise HTTPException(status_code=401, detail="Authentication failed")
    
    def _get_client_id(self, request: Request) -> str:
        """Get client ID for rate limiting."""
        # Use IP address as client ID (simplified)
        return request.client.host if request.client else "unknown"
    
    async def _get_cached_response(self, request: Request, ttl: int) -> Optional[Response]:
        """Get cached response."""
        try:
            cache_key = f"gateway_cache:{request.url}:{request.method}"
            cached_data = self.cache.get(cache_key)
            
            if cached_data:
                return JSONResponse(
                    content=cached_data["content"],
                    status_code=cached_data["status_code"],
                    headers=cached_data["headers"]
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting cached response: {e}")
            return None
    
    async def _cache_response(self, request: Request, response: Response, ttl: int):
        """Cache response."""
        try:
            if response.status_code != 200:
                return
            
            cache_key = f"gateway_cache:{request.url}:{request.method}"
            
            # Get response content
            if hasattr(response, 'body'):
                content = response.body.decode('utf-8')
            else:
                content = str(response.body)
            
            cache_data = {
                "content": json.loads(content) if content else {},
                "status_code": response.status_code,
                "headers": dict(response.headers)
            }
            
            self.cache.set(cache_key, cache_data, ttl)
            
        except Exception as e:
            self.logger.error(f"Error caching response: {e}")
    
    async def _proxy_request(self, request: Request, route: RouteConfig) -> Response:
        """Proxy request to service."""
        try:
            service = self.services[route.service_endpoint]
            
            if not service.enabled:
                raise HTTPException(status_code=503, detail="Service unavailable")
            
            # Build target URL
            target_url = f"{service.base_url}{request.url.path}"
            if request.url.query:
                target_url += f"?{request.url.query}"
            
            # Get circuit breaker
            circuit_breaker = self.circuit_breakers[route.service_endpoint]
            
            # Make request through circuit breaker
            async def make_request():
                # Prepare headers
                headers = dict(request.headers)
                headers.pop("host", None)  # Remove host header
                
                # Make request
                response = await self.http_client.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    content=await request.body(),
                    timeout=service.timeout
                )
                
                return response
            
            # Execute with circuit breaker
            service_response = await circuit_breaker.call(make_request)
            
            # Return response
            return Response(
                content=service_response.content,
                status_code=service_response.status_code,
                headers=dict(service_response.headers)
            )
            
        except Exception as e:
            self.logger.error(f"Error proxying request: {e}")
            raise HTTPException(status_code=502, detail="Service unavailable")
    
    async def _aggregate_request(self, request: Request, route: RouteConfig) -> Response:
        """Aggregate responses from multiple services."""
        try:
            if not route.aggregation_services:
                raise HTTPException(status_code=500, detail="No aggregation services configured")
            
            # Make requests to all services
            tasks = []
            for service_name in route.aggregation_services:
                task = self._call_service(service_name, request)
                tasks.append(task)
            
            # Wait for all responses
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Aggregate responses
            aggregated_data = {}
            
            for i, response in enumerate(responses):
                service_name = route.aggregation_services[i]
                
                if isinstance(response, Exception):
                    self.logger.error(f"Error calling service {service_name}: {response}")
                    aggregated_data[service_name] = {"error": str(response)}
                else:
                    try:
                        content = response.json()
                        aggregated_data[service_name] = content
                    except:
                        aggregated_data[service_name] = {"raw_response": response.text}
            
            # Return aggregated response
            return JSONResponse(content=aggregated_data)
            
        except Exception as e:
            self.logger.error(f"Error aggregating request: {e}")
            raise HTTPException(status_code=500, detail="Aggregation failed")
    
    async def _transform_request(self, request: Request, route: RouteConfig) -> Response:
        """Transform request/response."""
        # This would implement request/response transformation
        # For now, just proxy
        return await self._proxy_request(request, route)
    
    async def _call_service(self, service_name: str, request: Request) -> httpx.Response:
        """Call a specific service."""
        service = self.services[service_name]
        circuit_breaker = self.circuit_breakers[service_name]
        
        target_url = f"{service.base_url}{request.url.path}"
        if request.url.query:
            target_url += f"?{request.url.query}"
        
        async def make_request():
            headers = dict(request.headers)
            headers.pop("host", None)
            
            return await self.http_client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=await request.body(),
                timeout=service.timeout
            )
        
        return await circuit_breaker.call(make_request)
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for API Gateway and all services."""
        try:
            gateway_health = {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "services": {}
            }
            
            # Check all services
            for service_name, service in self.services.items():
                try:
                    circuit_breaker = self.circuit_breakers[service_name]
                    
                    health_url = f"{service.base_url}{service.health_endpoint}"
                    response = await self.http_client.get(health_url, timeout=5)
                    
                    service_health = {
                        "status": "healthy" if response.status_code == 200 else "unhealthy",
                        "circuit_breaker": circuit_breaker.get_state().to_dict(),
                        "response_time": response.elapsed.total_seconds() if hasattr(response, 'elapsed') else None
                    }
                    
                except Exception as e:
                    service_health = {
                        "status": "unhealthy",
                        "error": str(e),
                        "circuit_breaker": circuit_breaker.get_state().to_dict()
                    }
                
                gateway_health["services"][service_name] = service_health
            
            # Check if any services are unhealthy
            unhealthy_services = [
                name for name, health in gateway_health["services"].items()
                if health["status"] != "healthy"
            ]
            
            if unhealthy_services:
                gateway_health["status"] = "degraded"
                gateway_health["unhealthy_services"] = unhealthy_services
            
            return gateway_health
            
        except Exception as e:
            self.logger.error(f"Error in health check: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get API Gateway statistics."""
        try:
            return {
                "services": {
                    name: {
                        "enabled": service.enabled,
                        "circuit_breaker": self.circuit_breakers[name].get_state().to_dict()
                    }
                    for name, service in self.services.items()
                },
                "routes": {
                    key: route.to_dict()
                    for key, route in self.routes.items()
                },
                "metrics": {
                    "request_count": self.request_count._value.get(),
                    "active_connections": self.active_connections._value.get()
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {}


# FastAPI application
app = FastAPI(
    title="Sentinel Trading API Gateway",
    description="API Gateway for Sentinel Trading microservices",
    version="1.0.0"
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Global API Gateway instance
api_gateway = APIGateway()

security = HTTPBearer()


@app.middleware("http")
async def gateway_middleware(request: Request, call_next):
    """Gateway middleware for request routing."""
    # Increment active connections
    api_gateway.active_connections.inc()
    
    try:
        # Route request
        if request.url.path.startswith("/health") or request.url.path.startswith("/metrics"):
            # Bypass routing for health and metrics endpoints
            response = await call_next(request)
        else:
            response = await api_gateway.route_request(request)
        
        return response
    finally:
        # Decrement active connections
        api_gateway.active_connections.dec()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return await api_gateway.health_check()


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type="text/plain")


@app.get("/gateway/stats")
async def gateway_stats():
    """Gateway statistics endpoint."""
    return api_gateway.get_statistics()


# Proxy all other requests
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_request(request: Request, path: str):
    """Proxy request to appropriate service."""
    return await api_gateway.route_request(request)


# Utility functions
def run_api_gateway(host: str = "0.0.0.0", port: int = 8000):
    """Run the API Gateway."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


# Main execution
if __name__ == "__main__":
    run_api_gateway()
