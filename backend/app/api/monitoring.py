"""
API monitoring and response time tracking endpoints.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import Blueprint, jsonify, request, g
from prometheus_client import CONTENT_TYPE_LATEST

from app.infrastructure.metrics import get_metrics, metrics_endpoint
from app.infrastructure.error_reporting import get_error_reporter
from app.infrastructure.logging_config import LoggerMixin

logger = logging.getLogger(__name__)

monitoring_bp = Blueprint('monitoring', __name__, url_prefix='/monitoring')


class APIMonitor(LoggerMixin):
    """API monitoring and performance tracking."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.error_reporter = get_error_reporter()
        self.request_times = {}  # In-memory cache for recent requests
        self.max_requests = 1000
    
    def record_request_time(self, endpoint: str, method: str, duration: float, status_code: int):
        """Record request time for monitoring."""
        try:
            # Record in Prometheus
            self.metrics.record_request(method, endpoint, status_code, duration)
            
            # Store in memory for recent analysis
            timestamp = datetime.utcnow()
            request_key = f"{method}:{endpoint}"
            
            if request_key not in self.request_times:
                self.request_times[request_key] = []
            
            self.request_times[request_key].append({
                'timestamp': timestamp,
                'duration': duration,
                'status_code': status_code
            })
            
            # Keep only recent requests
            cutoff_time = timestamp - timedelta(hours=1)
            self.request_times[request_key] = [
                req for req in self.request_times[request_key] 
                if req['timestamp'] > cutoff_time
            ]
            
            # Limit total requests per endpoint
            if len(self.request_times[request_key]) > self.max_requests:
                self.request_times[request_key] = self.request_times[request_key][-self.max_requests:]
            
            # Log slow requests
            if duration > 2.0:  # Log requests over 2 seconds
                self.logger.warning(f"Slow request: {method} {endpoint} - {duration:.2f}s")
                
                # Add breadcrumb to error reporting
                self.error_reporter.add_performance_breadcrumb(
                    operation=f"{method} {endpoint}",
                    duration_ms=duration * 1000,
                    extra={
                        'status_code': status_code,
                        'slow_request': True
                    }
                )
        
        except Exception as e:
            self.logger.error(f"Failed to record request time: {e}")
    
    def get_endpoint_stats(self, endpoint: str = None, hours: int = 1) -> Dict[str, Any]:
        """Get statistics for endpoint(s)."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            stats = {}
            
            endpoints_to_check = [endpoint] if endpoint else list(self.request_times.keys())
            
            for ep in endpoints_to_check:
                if ep not in self.request_times:
                    continue
                
                recent_requests = [
                    req for req in self.request_times[ep]
                    if req['timestamp'] > cutoff_time
                ]
                
                if not recent_requests:
                    continue
                
                durations = [req['duration'] for req in recent_requests]
                status_codes = [req['status_code'] for req in recent_requests]
                
                stats[ep] = {
                    'request_count': len(recent_requests),
                    'avg_duration_ms': sum(durations) / len(durations) * 1000,
                    'min_duration_ms': min(durations) * 1000,
                    'max_duration_ms': max(durations) * 1000,
                    'p95_duration_ms': self._percentile(durations, 0.95) * 1000,
                    'p99_duration_ms': self._percentile(durations, 0.99) * 1000,
                    'success_rate': len([s for s in status_codes if 200 <= s < 300]) / len(status_codes),
                    'error_rate': len([s for s in status_codes if s >= 400]) / len(status_codes),
                    'status_distribution': self._get_status_distribution(status_codes),
                    'requests_per_minute': len(recent_requests) / hours * 60,
                }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get endpoint stats: {e}")
            return {}
    
    def get_slow_requests(self, threshold_ms: float = 1000, hours: int = 1) -> List[Dict[str, Any]]:
        """Get slow requests above threshold."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            slow_requests = []
            
            for endpoint, requests in self.request_times.items():
                for req in requests:
                    if req['timestamp'] > cutoff_time and req['duration'] * 1000 > threshold_ms:
                        slow_requests.append({
                            'endpoint': endpoint,
                            'timestamp': req['timestamp'].isoformat(),
                            'duration_ms': req['duration'] * 1000,
                            'status_code': req['status_code']
                        })
            
            # Sort by duration (slowest first)
            slow_requests.sort(key=lambda x: x['duration_ms'], reverse=True)
            
            return slow_requests[:100]  # Limit to 100 slowest requests
            
        except Exception as e:
            self.logger.error(f"Failed to get slow requests: {e}")
            return []
    
    def get_error_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Get error trends over time."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            errors_by_hour = {}
            
            for endpoint, requests in self.request_times.items():
                for req in requests:
                    if req['timestamp'] > cutoff_time and req['status_code'] >= 400:
                        hour = req['timestamp'].replace(minute=0, second=0, microsecond=0)
                        hour_key = hour.isoformat()
                        
                        if hour_key not in errors_by_hour:
                            errors_by_hour[hour_key] = []
                        
                        errors_by_hour[hour_key].append({
                            'endpoint': endpoint,
                            'status_code': req['status_code'],
                            'duration_ms': req['duration'] * 1000
                        })
            
            # Calculate trends
            trends = {}
            for hour, errors in errors_by_hour.items():
                trends[hour] = {
                    'error_count': len(errors),
                    'unique_endpoints': len(set(e['endpoint'] for e in errors)),
                    'avg_duration_ms': sum(e['duration_ms'] for e in errors) / len(errors),
                    'status_distribution': self._get_status_distribution([e['status_code'] for e in errors])
                }
            
            return trends
            
        except Exception as e:
            self.logger.error(f"Failed to get error trends: {e}")
            return {}
    
    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile of values."""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def _get_status_distribution(self, status_codes: List[int]) -> Dict[str, int]:
        """Get distribution of status codes."""
        distribution = {}
        
        for code in status_codes:
            category = self._get_status_category(code)
            distribution[category] = distribution.get(category, 0) + 1
        
        return distribution
    
    def _get_status_category(self, status_code: int) -> str:
        """Get category for HTTP status code."""
        if 200 <= status_code < 300:
            return '2xx_success'
        elif 300 <= status_code < 400:
            return '3xx_redirect'
        elif 400 <= status_code < 500:
            return '4xx_client_error'
        elif 500 <= status_code < 600:
            return '5xx_server_error'
        else:
            return 'unknown'


# Global API monitor instance
api_monitor = APIMonitor()


@monitoring_bp.route('/prometheus')
def prometheus_metrics():
    """Expose Prometheus metrics."""
    return metrics_endpoint()


@monitoring_bp.route('/endpoints')
def endpoint_stats():
    """Get endpoint performance statistics."""
    try:
        endpoint = request.args.get('endpoint')
        hours = request.args.get('hours', 1, type=int)
        
        stats = api_monitor.get_endpoint_stats(endpoint, hours)
        
        return jsonify({
            'endpoint': endpoint,
            'hours': hours,
            'stats': stats,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get endpoint stats: {e}")
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@monitoring_bp.route('/slow-requests')
def slow_requests():
    """Get slow requests above threshold."""
    try:
        threshold_ms = request.args.get('threshold_ms', 1000, type=float)
        hours = request.args.get('hours', 1, type=int)
        
        slow_requests = api_monitor.get_slow_requests(threshold_ms, hours)
        
        return jsonify({
            'threshold_ms': threshold_ms,
            'hours': hours,
            'slow_requests': slow_requests,
            'count': len(slow_requests),
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get slow requests: {e}")
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@monitoring_bp.route('/error-trends')
def error_trends():
    """Get error trends over time."""
    try:
        hours = request.args.get('hours', 24, type=int)
        
        trends = api_monitor.get_error_trends(hours)
        
        return jsonify({
            'hours': hours,
            'trends': trends,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get error trends: {e}")
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@monitoring_bp.route('/performance-summary')
def performance_summary():
    """Get overall performance summary."""
    try:
        hours = request.args.get('hours', 1, type=int)
        
        # Get overall stats
        stats = api_monitor.get_endpoint_stats(hours=hours)
        
        # Calculate summary metrics
        total_requests = sum(s['request_count'] for s in stats.values())
        total_errors = sum(s['request_count'] * s['error_rate'] for s in stats.values())
        
        # Find slowest endpoint
        slowest_endpoint = None
        slowest_time = 0
        
        for endpoint, stat in stats.items():
            if stat['avg_duration_ms'] > slowest_time:
                slowest_time = stat['avg_duration_ms']
                slowest_endpoint = endpoint
        
        # Find highest error rate
        worst_error_endpoint = None
        worst_error_rate = 0
        
        for endpoint, stat in stats.items():
            if stat['error_rate'] > worst_error_rate:
                worst_error_rate = stat['error_rate']
                worst_error_endpoint = endpoint
        
        summary = {
            'hours': hours,
            'total_requests': total_requests,
            'total_errors': int(total_errors),
            'overall_error_rate': total_errors / total_requests if total_requests > 0 else 0,
            'slowest_endpoint': {
                'endpoint': slowest_endpoint,
                'avg_duration_ms': slowest_time
            },
            'worst_error_endpoint': {
                'endpoint': worst_error_endpoint,
                'error_rate': worst_error_rate
            },
            'endpoint_count': len(stats),
            'avg_response_time_ms': sum(s['avg_duration_ms'] for s in stats.values()) / len(stats) if stats else 0,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return jsonify(summary)
        
    except Exception as e:
        logger.error(f"Failed to get performance summary: {e}")
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@monitoring_bp.route('/alerts')
def performance_alerts():
    """Get performance alerts based on thresholds."""
    try:
        alerts = []
        hours = 1  # Check last hour
        
        stats = api_monitor.get_endpoint_stats(hours=hours)
        
        # Check for high error rates
        for endpoint, stat in stats.items():
            if stat['error_rate'] > 0.1:  # 10% error rate
                alerts.append({
                    'type': 'high_error_rate',
                    'severity': 'critical' if stat['error_rate'] > 0.2 else 'warning',
                    'endpoint': endpoint,
                    'error_rate': stat['error_rate'],
                    'message': f"High error rate ({stat['error_rate']:.1%}) for {endpoint}"
                })
            
            # Check for slow response times
            if stat['p95_duration_ms'] > 2000:  # 2 seconds
                alerts.append({
                    'type': 'slow_response',
                    'severity': 'critical' if stat['p95_duration_ms'] > 5000 else 'warning',
                    'endpoint': endpoint,
                    'p95_duration_ms': stat['p95_duration_ms'],
                    'message': f"Slow response time (P95: {stat['p95_duration_ms']:.0f}ms) for {endpoint}"
                })
        
        # Check for no recent requests (potential downtime)
        if not stats:
            alerts.append({
                'type': 'no_requests',
                'severity': 'critical',
                'endpoint': 'all',
                'message': 'No requests received in the last hour'
            })
        
        return jsonify({
            'alerts': alerts,
            'alert_count': len(alerts),
            'hours_checked': hours,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get performance alerts: {e}")
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@monitoring_bp.route('/health')
def monitoring_health():
    """Health check for monitoring system."""
    try:
        # Check if monitoring is working
        stats = api_monitor.get_endpoint_stats(hours=1)
        
        health = {
            'status': 'healthy',
            'monitoring_active': True,
            'endpoints_tracked': len(stats),
            'recent_requests': sum(s['request_count'] for s in stats.values()),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return jsonify(health), 200
        
    except Exception as e:
        logger.error(f"Monitoring health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


# Middleware for automatic request monitoring
def request_monitor_middleware(app):
    """Add request monitoring middleware to Flask app."""
    
    @app.before_request
    def before_request():
        g.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        if hasattr(g, 'start_time'):
            duration = time.time() - g.start_time
            endpoint = request.endpoint or request.path
            method = request.method
            status_code = response.status_code
            
            api_monitor.record_request_time(endpoint, method, duration, status_code)
        
        return response
    
    return app


def get_api_monitor() -> APIMonitor:
    """Get global API monitor instance."""
    return api_monitor
