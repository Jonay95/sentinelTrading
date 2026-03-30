"""
Sentry integration for structured error reporting and monitoring.
"""

import logging
import os
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, List
from flask import Flask, request, g
from sentry_sdk import Hub, configure_scope, capture_exception, capture_message, add_breadcrumb
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

from app.infrastructure.logging_config import LoggerMixin

logger = logging.getLogger(__name__)


class ErrorReporter(LoggerMixin):
    """Enhanced error reporting with Sentry integration."""
    
    def __init__(self, app: Flask = None, dsn: str = None):
        self.app = app
        self.dsn = dsn or os.environ.get('SENTRY_DSN')
        self.enabled = bool(self.dsn)
        
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize Sentry with Flask app."""
        if not self.enabled:
            self.logger.warning("Sentry DSN not configured, error reporting disabled")
            return
        
        try:
            import sentry_sdk
            
            sentry_sdk.init(
                dsn=self.dsn,
                integrations=[
                    FlaskIntegration(
                        transaction_style="endpoint",
                        request_bodies="medium",
                        capture_headers=True,
                    ),
                    SqlalchemyIntegration(
                        engine=None,  # Will be automatically detected
                        capture_queries=True,
                        capture_query_params=True,
                    ),
                    RedisIntegration(
                        capture_commands=True,
                        capture_command_params=True,
                    ),
                    CeleryIntegration(
                        monitor_beat_tasks=True,
                        propagate_traces=True,
                    ),
                ],
                traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
                environment=os.environ.get('SENTRY_ENVIRONMENT', 'development'),
                release=os.environ.get('APP_VERSION', '1.0.0'),
                debug=app.debug if hasattr(app, 'debug') else False,
                attach_stacktrace=True,
                before_send=self._before_send,
                before_breadcrumb=self._before_breadcrumb,
                ignore_errors=[
                    # Common errors to ignore
                    'KeyboardInterrupt',
                    'SystemExit',
                    'ConnectionError',
                    'TimeoutError',
                ] if os.environ.get('SENTRY_IGNORE_COMMON_ERRORS', 'true').lower() == 'true' else [],
            )
            
            # Set up Flask request hooks
            self._setup_flask_hooks(app)
            
            self.logger.info("Sentry error reporting initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Sentry: {e}")
    
    def _setup_flask_hooks(self, app: Flask):
        """Setup Flask hooks for enhanced error reporting."""
        
        @app.before_request
        def before_request():
            """Add request context to Sentry."""
            g.request_start_time = datetime.utcnow()
            g.request_id = self._generate_request_id()
            
            # Add breadcrumb for request start
            self.add_breadcrumb(
                category='request',
                message=f"Request started: {request.method} {request.path}",
                level='info',
                data={
                    'method': request.method,
                    'path': request.path,
                    'query_params': dict(request.args),
                    'user_agent': request.headers.get('User-Agent'),
                    'remote_addr': request.remote_addr,
                    'request_id': g.request_id,
                }
            )
        
        @app.after_request
        def after_request(response):
            """Add response context to Sentry."""
            if hasattr(g, 'request_start_time'):
                duration = (datetime.utcnow() - g.request_start_time).total_seconds()
                
                # Add breadcrumb for request completion
                self.add_breadcrumb(
                    category='request',
                    message=f"Request completed: {request.method} {request.path} - {response.status_code}",
                    level='info',
                    data={
                        'method': request.method,
                        'path': request.path,
                        'status_code': response.status_code,
                        'duration_ms': duration * 1000,
                        'request_id': getattr(g, 'request_id', 'unknown'),
                    }
                )
            
            return response
        
        @app.errorhandler(Exception)
        def handle_exception(error):
            """Handle exceptions and report to Sentry."""
            self.capture_exception(error, extra={
                'endpoint': request.endpoint,
                'method': request.method,
                'path': request.path,
                'request_id': getattr(g, 'request_id', 'unknown'),
            })
            
            # Re-raise the exception to let Flask handle it
            raise error
    
    def _before_send(self, event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process events before sending to Sentry."""
        try:
            # Add custom tags
            if 'tags' not in event:
                event['tags'] = {}
            
            event['tags'].update({
                'service': 'sentinel-trading-api',
                'environment': os.environ.get('SENTRY_ENVIRONMENT', 'development'),
            })
            
            # Add extra context
            if 'extra' not in event:
                event['extra'] = {}
            
            # Add request context if available
            if hasattr(g, 'request_id'):
                event['extra']['request_id'] = g.request_id
            
            # Add system information
            event['extra']['system_info'] = self._get_system_info()
            
            # Filter sensitive data
            event = self._filter_sensitive_data(event)
            
            return event
            
        except Exception as e:
            self.logger.error(f"Error in before_send: {e}")
            return event
    
    def _before_breadcrumb(self, breadcrumb: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process breadcrumbs before adding to Sentry."""
        try:
            # Filter sensitive data from breadcrumbs
            if 'data' in breadcrumb:
                breadcrumb['data'] = self._filter_sensitive_data(breadcrumb['data'])
            
            return breadcrumb
            
        except Exception as e:
            self.logger.error(f"Error in before_breadcrumb: {e}")
            return breadcrumb
    
    def capture_exception(self, error: Exception, extra: Dict[str, Any] = None, tags: Dict[str, str] = None):
        """Capture exception with additional context."""
        if not self.enabled:
            return
        
        try:
            with configure_scope() as scope:
                if extra:
                    scope.set_extra("custom_data", extra)
                
                if tags:
                    for key, value in tags.items():
                        scope.set_tag(key, value)
                
                # Add error classification
                error_type = type(error).__name__
                scope.set_tag("error_type", error_type)
                scope.set_tag("error_severity", self._classify_error_severity(error))
                
                capture_exception(error)
                
        except Exception as e:
            self.logger.error(f"Failed to capture exception: {e}")
    
    def capture_message(self, message: str, level: str = "info", extra: Dict[str, Any] = None, tags: Dict[str, str] = None):
        """Capture message with additional context."""
        if not self.enabled:
            return
        
        try:
            with configure_scope() as scope:
                if extra:
                    scope.set_extra("custom_data", extra)
                
                if tags:
                    for key, value in tags.items():
                        scope.set_tag(key, value)
                
                capture_message(message, level=level)
                
        except Exception as e:
            self.logger.error(f"Failed to capture message: {e}")
    
    def add_breadcrumb(self, category: str, message: str, level: str = "info", data: Dict[str, Any] = None):
        """Add breadcrumb to Sentry context."""
        if not self.enabled:
            return
        
        try:
            add_breadcrumb(
                category=category,
                message=message,
                level=level,
                data=data or {}
            )
            
        except Exception as e:
            self.logger.error(f"Failed to add breadcrumb: {e}")
    
    def set_user_context(self, user_id: str, email: str = None, username: str = None, extra: Dict[str, Any] = None):
        """Set user context for error reporting."""
        if not self.enabled:
            return
        
        try:
            user_data = {"id": user_id}
            
            if email:
                user_data["email"] = email
            
            if username:
                user_data["username"] = username
            
            if extra:
                user_data.update(extra)
            
            with configure_scope() as scope:
                scope.set_user(user_data)
                
        except Exception as e:
            self.logger.error(f"Failed to set user context: {e}")
    
    def set_transaction_context(self, transaction_name: str, operation: str = None, extra: Dict[str, Any] = None):
        """Set transaction context for performance monitoring."""
        if not self.enabled:
            return
        
        try:
            with configure_scope() as scope:
                scope.set_transaction(transaction_name)
                
                if operation:
                    scope.set_tag("operation", operation)
                
                if extra:
                    for key, value in extra.items():
                        scope.set_extra(key, value)
                
        except Exception as e:
            self.logger.error(f"Failed to set transaction context: {e}")
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        import uuid
        return str(uuid.uuid4())
    
    def _classify_error_severity(self, error: Exception) -> str:
        """Classify error severity for Sentry."""
        error_type = type(error).__name__
        
        # Critical errors that should be alerted immediately
        critical_errors = [
            'DatabaseError', 'ConnectionError', 'TimeoutError',
            'MemoryError', 'SystemError', 'OSError'
        ]
        
        # Warning-level errors
        warning_errors = [
            'ValidationError', 'AuthenticationError', 'AuthorizationError',
            'NotFoundError', 'PermissionError'
        ]
        
        if error_type in critical_errors:
            return 'critical'
        elif error_type in warning_errors:
            return 'warning'
        else:
            return 'error'
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information for error context."""
        try:
            import psutil
            import platform
            
            return {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "cpu_count": psutil.cpu_count(),
                "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                "disk_usage_gb": round(psutil.disk_usage('/').used / (1024**3), 2),
                "process_id": os.getpid(),
            }
        except Exception as e:
            self.logger.error(f"Failed to get system info: {e}")
            return {"error": str(e)}
    
    def _filter_sensitive_data(self, data: Any) -> Any:
        """Filter sensitive data from Sentry events."""
        if isinstance(data, dict):
            filtered = {}
            for key, value in data.items():
                if self._is_sensitive_key(key):
                    filtered[key] = "[FILTERED]"
                elif isinstance(value, (dict, list)):
                    filtered[key] = self._filter_sensitive_data(value)
                else:
                    filtered[key] = value
            return filtered
        elif isinstance(data, list):
            return [self._filter_sensitive_data(item) for item in data]
        else:
            return data
    
    def _is_sensitive_key(self, key: str) -> bool:
        """Check if a key contains sensitive information."""
        sensitive_patterns = [
            'password', 'token', 'secret', 'key', 'auth',
            'credential', 'private', 'session', 'cookie',
            'api_key', 'dsn', 'database_url', 'redis_url'
        ]
        
        return any(pattern in key.lower() for pattern in sensitive_patterns)
    
    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get error summary for the last N hours."""
        if not self.enabled:
            return {"enabled": False}
        
        try:
            # This would require Sentry API integration
            # For now, return placeholder data
            return {
                "enabled": True,
                "hours": hours,
                "message": "Error summary requires Sentry API integration",
                "placeholder": {
                    "total_errors": 0,
                    "error_types": {},
                    "most_common_errors": [],
                    "trend": "stable"
                }
            }
        except Exception as e:
            self.logger.error(f"Failed to get error summary: {e}")
            return {"enabled": True, "error": str(e)}


# Decorators for automatic error reporting
def report_errors(operation: str = None, extra: Dict[str, Any] = None):
    """Decorator to automatically report errors to Sentry."""
    def decorator(f):
        def decorated_function(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                error_reporter.capture_exception(
                    e,
                    extra={
                        "function": f.__name__,
                        "operation": operation or f.__name__,
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys()),
                        **(extra or {})
                    },
                    tags={
                        "decorator": "report_errors",
                        "function": f.__name__,
                    }
                )
                raise
        return decorated_function
    return decorator


def track_transaction(operation: str, extra: Dict[str, Any] = None):
    """Decorator to track transactions in Sentry."""
    def decorator(f):
        def decorated_function(*args, **kwargs):
            transaction_name = f"{f.__module__}.{f.__name__}"
            
            error_reporter.set_transaction_context(
                transaction_name=transaction_name,
                operation=operation,
                extra=extra or {}
            )
            
            try:
                return f(*args, **kwargs)
            except Exception as e:
                error_reporter.capture_exception(
                    e,
                    extra={
                        "transaction": transaction_name,
                        "operation": operation,
                        **(extra or {})
                    }
                )
                raise
        return decorated_function
    return decorator


# Global error reporter instance
error_reporter = ErrorReporter()


def init_error_reporting(app: Flask = None, dsn: str = None) -> ErrorReporter:
    """Initialize error reporting."""
    global error_reporter
    error_reporter = ErrorReporter(app, dsn)
    return error_reporter


def get_error_reporter() -> ErrorReporter:
    """Get global error reporter instance."""
    return error_reporter


# Helper functions for common error reporting patterns
def report_api_error(error: Exception, endpoint: str, method: str, user_id: str = None):
    """Report API-related error."""
    error_reporter.capture_exception(
        error,
        extra={
            "endpoint": endpoint,
            "method": method,
            "query_params": dict(request.args) if request else {},
            "headers": dict(request.headers) if request else {},
        },
        tags={
            "error_type": "api_error",
            "endpoint": endpoint,
            "method": method,
        }
    )
    
    if user_id:
        error_reporter.set_user_context(user_id)


def report_database_error(error: Exception, operation: str, table: str = None):
    """Report database-related error."""
    error_reporter.capture_exception(
        error,
        extra={
            "operation": operation,
            "table": table,
            "query": str(error) if hasattr(error, 'query') else None,
        },
        tags={
            "error_type": "database_error",
            "operation": operation,
            "table": table or "unknown",
        }
    )


def report_external_api_error(error: Exception, service: str, endpoint: str = None):
    """Report external API-related error."""
    error_reporter.capture_exception(
        error,
        extra={
            "service": service,
            "endpoint": endpoint,
            "status_code": getattr(error, 'response', {}).get('status_code') if hasattr(error, 'response') else None,
        },
        tags={
            "error_type": "external_api_error",
            "service": service,
            "endpoint": endpoint or "unknown",
        }
    )


def report_celery_error(error: Exception, task_name: str, task_id: str = None):
    """Report Celery task-related error."""
    error_reporter.capture_exception(
        error,
        extra={
            "task_name": task_name,
            "task_id": task_id,
            "traceback": traceback.format_exc(),
        },
        tags={
            "error_type": "celery_error",
            "task_name": task_name,
        }
    )


def add_performance_breadcrumb(operation: str, duration_ms: float, extra: Dict[str, Any] = None):
    """Add performance-related breadcrumb."""
    error_reporter.add_breadcrumb(
        category='performance',
        message=f"Operation: {operation} ({duration_ms:.2f}ms)",
        level='info',
        data={
            "operation": operation,
            "duration_ms": duration_ms,
            **(extra or {})
        }
    )


def add_business_breadcrumb(event_type: str, asset_symbol: str = None, extra: Dict[str, Any] = None):
    """Add business-related breadcrumb."""
    error_reporter.add_breadcrumb(
        category='business',
        message=f"Business event: {event_type}",
        level='info',
        data={
            "event_type": event_type,
            "asset_symbol": asset_symbol,
            **(extra or {})
        }
    )
