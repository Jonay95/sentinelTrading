"""
Prometheus metrics collection for Sentinel Trading application.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.core import REGISTRY
from functools import wraps
from flask import request, g

from app.infrastructure.logging_config import LoggerMixin

logger = logging.getLogger(__name__)


class PrometheusMetrics(LoggerMixin):
    """Prometheus metrics collector for application monitoring."""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or REGISTRY
        
        # API metrics
        self.request_count = Counter(
            'sentinel_http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status_code'],
            registry=self.registry
        )
        
        self.request_duration = Histogram(
            'sentinel_http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'endpoint'],
            registry=self.registry
        )
        
        # Business metrics
        self.predictions_total = Counter(
            'sentinel_predictions_total',
            'Total predictions generated',
            ['asset_symbol', 'signal', 'confidence_range'],
            registry=self.registry
        )
        
        self.prediction_accuracy = Gauge(
            'sentinel_prediction_accuracy',
            'Prediction accuracy percentage',
            ['asset_symbol', 'time_window_days'],
            registry=self.registry
        )
        
        self.assets_tracked = Gauge(
            'sentinel_assets_tracked_total',
            'Total number of tracked assets',
            ['asset_type'],
            registry=self.registry
        )
        
        self.market_data_updates = Counter(
            'sentinel_market_data_updates_total',
            'Total market data updates',
            ['asset_symbol', 'data_source'],
            registry=self.registry
        )
        
        self.news_articles_processed = Counter(
            'sentinel_news_articles_processed_total',
            'Total news articles processed',
            ['source', 'sentiment_range'],
            registry=self.registry
        )
        
        # System metrics
        self.active_users = Gauge(
            'sentinel_active_users',
            'Number of active users',
            registry=self.registry
        )
        
        self.cache_operations = Counter(
            'sentinel_cache_operations_total',
            'Total cache operations',
            ['operation', 'result'],
            registry=self.registry
        )
        
        self.database_connections = Gauge(
            'sentinel_database_connections',
            'Number of active database connections',
            ['pool_type'],
            registry=self.registry
        )
        
        self.celery_tasks = Counter(
            'sentinel_celery_tasks_total',
            'Total Celery tasks',
            ['task_name', 'status'],
            registry=self.registry
        )
        
        self.celery_queue_size = Gauge(
            'sentinel_celery_queue_size',
            'Celery queue size',
            ['queue_name'],
            registry=self.registry
        )
        
        # External API metrics
        self.external_api_requests = Counter(
            'sentinel_external_api_requests_total',
            'Total external API requests',
            ['service', 'endpoint', 'status'],
            registry=self.registry
        )
        
        self.external_api_response_time = Histogram(
            'sentinel_external_api_response_time_seconds',
            'External API response time in seconds',
            ['service', 'endpoint'],
            registry=self.registry
        )
        
        # Error metrics
        self.errors_total = Counter(
            'sentinel_errors_total',
            'Total errors',
            ['error_type', 'component'],
            registry=self.registry
        )
        
        # Financial metrics
        self.portfolio_value = Gauge(
            'sentinel_portfolio_value',
            'Portfolio value in USD',
            ['portfolio_id'],
            registry=self.registry
        )
        
        self.trading_signals = Counter(
            'sentinel_trading_signals_total',
            'Total trading signals generated',
            ['signal_type', 'asset_symbol'],
            registry=self.registry
        )
    
    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Record HTTP request metrics."""
        self.request_count.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).inc()
        
        self.request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    def record_prediction(self, asset_symbol: str, signal: str, confidence: float):
        """Record prediction metrics."""
        confidence_range = self._get_confidence_range(confidence)
        self.predictions_total.labels(
            asset_symbol=asset_symbol,
            signal=signal,
            confidence_range=confidence_range
        ).inc()
    
    def record_prediction_accuracy(self, asset_symbol: str, accuracy: float, time_window_days: int):
        """Record prediction accuracy."""
        self.prediction_accuracy.labels(
            asset_symbol=asset_symbol,
            time_window_days=str(time_window_days)
        ).set(accuracy)
    
    def record_market_data_update(self, asset_symbol: str, data_source: str):
        """Record market data update."""
        self.market_data_updates.labels(
            asset_symbol=asset_symbol,
            data_source=data_source
        ).inc()
    
    def record_news_article(self, source: str, sentiment: float):
        """Record news article processing."""
        sentiment_range = self._get_sentiment_range(sentiment)
        self.news_articles_processed.labels(
            source=source,
            sentiment_range=sentiment_range
        ).inc()
    
    def record_cache_operation(self, operation: str, result: str):
        """Record cache operation."""
        self.cache_operations.labels(
            operation=operation,
            result=result
        ).inc()
    
    def record_database_connections(self, active: int, idle: int, total: int):
        """Record database connection metrics."""
        self.database_connections.labels(pool_type='active').set(active)
        self.database_connections.labels(pool_type='idle').set(idle)
        self.database_connections.labels(pool_type='total').set(total)
    
    def record_celery_task(self, task_name: str, status: str):
        """Record Celery task metrics."""
        self.celery_tasks.labels(
            task_name=task_name,
            status=status
        ).inc()
    
    def record_celery_queue_size(self, queue_name: str, size: int):
        """Record Celery queue size."""
        self.celery_queue_size.labels(queue_name=queue_name).set(size)
    
    def record_external_api_request(self, service: str, endpoint: str, status: str, duration: float):
        """Record external API request."""
        self.external_api_requests.labels(
            service=service,
            endpoint=endpoint,
            status=status
        ).inc()
        
        self.external_api_response_time.labels(
            service=service,
            endpoint=endpoint
        ).observe(duration)
    
    def record_error(self, error_type: str, component: str):
        """Record error metrics."""
        self.errors_total.labels(
            error_type=error_type,
            component=component
        ).inc()
    
    def record_trading_signal(self, signal_type: str, asset_symbol: str):
        """Record trading signal."""
        self.trading_signals.labels(
            signal_type=signal_type,
            asset_symbol=asset_symbol
        ).inc()
    
    def update_assets_tracked(self, asset_counts: Dict[str, int]):
        """Update tracked assets metrics."""
        for asset_type, count in asset_counts.items():
            self.assets_tracked.labels(asset_type=asset_type).set(count)
    
    def update_active_users(self, count: int):
        """Update active users metric."""
        self.active_users.set(count)
    
    def update_portfolio_value(self, portfolio_id: str, value: float):
        """Update portfolio value."""
        self.portfolio_value.labels(portfolio_id=portfolio_id).set(value)
    
    def _get_confidence_range(self, confidence: float) -> str:
        """Get confidence range for metrics."""
        if confidence >= 0.8:
            return 'high'
        elif confidence >= 0.6:
            return 'medium'
        elif confidence >= 0.4:
            return 'low'
        else:
            return 'very_low'
    
    def _get_sentiment_range(self, sentiment: float) -> str:
        """Get sentiment range for metrics."""
        if sentiment >= 0.5:
            return 'positive'
        elif sentiment >= -0.5:
            return 'neutral'
        else:
            return 'negative'
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of current metrics."""
        try:
            summary = {}
            
            # Get prediction accuracy summary
            accuracy_samples = self.prediction_accuracy.collect()
            if accuracy_samples:
                summary['prediction_accuracy'] = {}
                for sample in accuracy_samples:
                    for metric in sample.samples:
                        asset_symbol = metric.labels.get('asset_symbol', 'unknown')
                        time_window = metric.labels.get('time_window_days', 'unknown')
                        summary['prediction_accuracy'][f"{asset_symbol}_{time_window}"] = metric.value
            
            # Get asset counts
            asset_samples = self.assets_tracked.collect()
            if asset_samples:
                summary['assets_tracked'] = {}
                for sample in asset_samples:
                    for metric in sample.samples:
                        asset_type = metric.labels.get('asset_type', 'unknown')
                        summary['assets_tracked'][asset_type] = metric.value
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Failed to generate metrics summary: {e}")
            return {}


class MetricsCollector(LoggerMixin):
    """Collects metrics from various application components."""
    
    def __init__(self, prometheus_metrics: PrometheusMetrics):
        self.prometheus_metrics = prometheus_metrics
    
    def collect_database_metrics(self):
        """Collect database-related metrics."""
        try:
            from app.infrastructure.database import get_db_manager
            db_manager = get_db_manager()
            
            if db_manager:
                pool_status = db_manager.get_pool_status()
                if pool_status.get("status") == "active":
                    active = pool_status.get("checked_out", 0)
                    idle = pool_status.get("checked_in", 0)
                    total = pool_status.get("pool_size", 0)
                    
                    self.prometheus_metrics.record_database_connections(active, idle, total)
            
        except Exception as e:
            self.logger.error(f"Failed to collect database metrics: {e}")
    
    def collect_cache_metrics(self):
        """Collect cache-related metrics."""
        try:
            from app.infrastructure.cache import get_cache
            cache = get_cache()
            
            if cache and cache.is_connected():
                cache_info = cache.get_cache_info()
                if cache_info.get("connected"):
                    hit_rate = cache_info.get("hit_rate", 0)
                    used_memory = cache_info.get("used_memory", "0B")
                    
                    # Record cache hit rate as a gauge (convert Counter to Gauge logic)
                    # This would need a Gauge metric for hit rate
                    self.logger.info(f"Cache hit rate: {hit_rate}%, Memory: {used_memory}")
            
        except Exception as e:
            self.logger.error(f"Failed to collect cache metrics: {e}")
    
    def collect_celery_metrics(self):
        """Collect Celery-related metrics."""
        try:
            from app.infrastructure.celery_app import get_task_monitor
            task_monitor = get_task_monitor()
            
            # Get queue sizes
            queue_info = task_monitor.get_queue_info()
            for queue_name, info in queue_info.items():
                size = info.get("message_count", 0)
                self.prometheus_metrics.record_celery_queue_size(queue_name, size)
            
            # Get active tasks
            active_tasks = task_monitor.get_active_tasks()
            for task in active_tasks:
                task_name = task.get("name", "unknown")
                self.prometheus_metrics.record_celery_task(task_name, "active")
            
        except Exception as e:
            self.logger.error(f"Failed to collect Celery metrics: {e}")
    
    def collect_business_metrics(self):
        """Collect business-related metrics."""
        try:
            from app.container import get_container
            container = get_container()
            
            # Asset counts by type
            asset_repo = container.asset_repository()
            assets = asset_repo.get_all()
            
            asset_counts = {}
            for asset in assets:
                asset_type = asset.asset_type
                asset_counts[asset_type] = asset_counts.get(asset_type, 0) + 1
            
            self.prometheus_metrics.update_assets_tracked(asset_counts)
            
            # Recent prediction accuracy
            prediction_repo = container.prediction_repository()
            # This would require implementing accuracy calculation in repository
            # For now, we'll just log the intent
            self.logger.info("Collecting prediction accuracy metrics")
            
        except Exception as e:
            self.logger.error(f"Failed to collect business metrics: {e}")
    
    def collect_all_metrics(self):
        """Collect all metrics."""
        self.collect_database_metrics()
        self.collect_cache_metrics()
        self.collect_celery_metrics()
        self.collect_business_metrics()


# Global metrics instance
prometheus_metrics = PrometheusMetrics()
metrics_collector = MetricsCollector(prometheus_metrics)


def track_requests(f):
    """Decorator to track HTTP request metrics."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        
        try:
            response = f(*args, **kwargs)
            status_code = getattr(response, 'status_code', 200)
        except Exception as e:
            status_code = 500
            prometheus_metrics.record_error('http_exception', 'api')
            raise
        finally:
            duration = time.time() - start_time
            
            # Get request info from Flask context
            method = getattr(request, 'method', 'unknown')
            endpoint = getattr(request, 'endpoint', 'unknown')
            
            prometheus_metrics.record_request(method, endpoint, status_code, duration)
        
        return response
    
    return decorated_function


def track_external_api_call(service: str, endpoint: str):
    """Decorator to track external API calls."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time()
            status = 'success'
            
            try:
                result = f(*args, **kwargs)
                return result
            except Exception as e:
                status = 'error'
                prometheus_metrics.record_error('external_api_error', service)
                raise
            finally:
                duration = time.time() - start_time
                prometheus_metrics.record_external_api_request(service, endpoint, status, duration)
        
        return decorated_function
    return decorator


def init_metrics():
    """Initialize metrics collection."""
    logger.info("Initializing Prometheus metrics")
    
    # Start periodic metrics collection
    import threading
    import time
    
    def collect_metrics_periodically():
        """Collect metrics every 30 seconds."""
        while True:
            try:
                metrics_collector.collect_all_metrics()
                time.sleep(30)
            except Exception as e:
                logger.error(f"Periodic metrics collection failed: {e}")
                time.sleep(30)
    
    metrics_thread = threading.Thread(target=collect_metrics_periodically, daemon=True)
    metrics_thread.start()
    
    logger.info("Metrics collection initialized")


def get_metrics() -> PrometheusMetrics:
    """Get Prometheus metrics instance."""
    return prometheus_metrics


def get_metrics_collector() -> MetricsCollector:
    """Get metrics collector instance."""
    return metrics_collector


# Flask integration
def metrics_endpoint():
    """Flask endpoint to expose Prometheus metrics."""
    from flask import Response
    
    # Update metrics before serving
    metrics_collector.collect_all_metrics()
    
    return Response(
        generate_latest(registry=prometheus_metrics.registry),
        mimetype=CONTENT_TYPE_LATEST
    )


# Business metric helpers
def record_prediction_event(asset_symbol: str, signal: str, confidence: float):
    """Record a prediction event."""
    prometheus_metrics.record_prediction(asset_symbol, signal, confidence)


def record_market_data_update(asset_symbol: str, source: str):
    """Record a market data update."""
    prometheus_metrics.record_market_data_update(asset_symbol, source)


def record_news_processing(source: str, sentiment: float):
    """Record news processing."""
    prometheus_metrics.record_news_article(source, sentiment)


def record_trading_signal(signal_type: str, asset_symbol: str):
    """Record a trading signal."""
    prometheus_metrics.record_trading_signal(signal_type, asset_symbol)


def record_application_error(error_type: str, component: str):
    """Record an application error."""
    prometheus_metrics.record_error(error_type, component)
