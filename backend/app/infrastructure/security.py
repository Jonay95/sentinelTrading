"""
Security infrastructure for Sentinel Trading: rate limiting, validation, and secrets.
"""

import os
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from functools import wraps
from flask import Flask, request, jsonify, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from marshmallow import Schema, ValidationError, fields, validate
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiting configuration and management."""
    
    def __init__(self, app: Flask = None):
        self.app = app
        self.limiter = None
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize rate limiter with Flask app."""
        self.limiter = Limiter(
            app=app,
            key_func=get_remote_address,
            default_limits=["200 per day", "50 per hour"],
            storage_uri="memory://",
            headers_enabled=True,
            swallow_errors=False
        )
        
        # Configure specific limits for different endpoints
        self._configure_endpoint_limits()
    
    def _configure_endpoint_limits(self):
        """Configure rate limits for specific endpoints."""
        # API endpoints with stricter limits
        self.limiter.limit("10 per minute")(lambda: None)  # Will be applied to specific routes
        
        # Job endpoints (more restrictive)
        self.limiter.limit("5 per minute")(lambda: None)
        
        # Public endpoints
        self.limiter.limit("100 per hour")(lambda: None)


class InputValidator:
    """Input validation using Marshmallow schemas."""
    
    @staticmethod
    def validate_request(schema_class, data=None):
        """Decorator to validate request data against schema."""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                try:
                    # Get data from request
                    if data is not None:
                        request_data = data
                    elif request.is_json:
                        request_data = request.get_json()
                    else:
                        request_data = request.args.to_dict()
                    
                    # Validate against schema
                    schema = schema_class()
                    validated_data = schema.load(request_data)
                    
                    # Store validated data in Flask's g context
                    g.validated_data = validated_data
                    
                    return f(*args, **kwargs)
                    
                except ValidationError as e:
                    logger.warning(f"Validation error: {e.messages}")
                    return jsonify({
                        "error": "Validation failed",
                        "messages": e.messages,
                        "timestamp": datetime.utcnow().isoformat()
                    }), 400
                except Exception as e:
                    logger.error(f"Unexpected validation error: {e}")
                    return jsonify({
                        "error": "Invalid request format",
                        "timestamp": datetime.utcnow().isoformat()
                    }), 400
            
            return decorated_function
        return decorator


# Marshmallow Schemas
class AssetSchema(Schema):
    """Schema for asset validation."""
    symbol = fields.Str(required=True, validate=validate.Length(min=1, max=10))
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    asset_type = fields.Str(required=True, validate=validate.OneOf(['crypto', 'stock', 'commodity']))
    external_id = fields.Str(allow_none=True, validate=validate.Length(max=50))
    provider = fields.Str(required=True, validate=validate.OneOf(['coingecko', 'yahoo', 'manual']))
    news_keywords = fields.Str(allow_none=True, validate=validate.Length(max=200))


class PredictionRequestSchema(Schema):
    """Schema for prediction requests."""
    asset_id = fields.Int(required=True, validate=validate.Range(min=1))
    horizon_days = fields.Int(allow_none=True, validate=validate.Range(min=1, max=365))
    ensemble = fields.Bool(allow_none=True)


class NewsQuerySchema(Schema):
    """Schema for news queries."""
    asset_id = fields.Int(allow_none=True, validate=validate.Range(min=1))
    limit = fields.Int(allow_none=True, validate=validate.Range(min=1, max=100))
    keywords = fields.Str(allow_none=True, validate=validate.Length(max=100))


class WalkForwardSchema(Schema):
    """Schema for walk-forward analysis."""
    asset_id = fields.Int(allow_none=True, validate=validate.Range(min=1))
    train_min = fields.Int(allow_none=True, validate=validate.Range(min=20, max=500))
    step = fields.Int(allow_none=True, validate=validate.Range(min=1, max=30))
    ensemble = fields.Bool(allow_none=True)


class SecretsManager:
    """Secure secrets management with encryption."""
    
    def __init__(self, app: Flask = None):
        self.app = app
        self._fernet = None
        self._key = None
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize secrets manager with Flask app."""
        # Try to get encryption key from environment or generate one
        key = os.environ.get('ENCRYPTION_KEY')
        if key:
            self._key = key.encode()
        else:
            # Generate a new key (in production, this should be stored securely)
            self._key = Fernet.generate_key()
            logger.warning("Generated new encryption key - in production, store this securely!")
        
        self._fernet = Fernet(self._key)
        
        # Store key in app config for access
        app.config['ENCRYPTION_KEY'] = self._key.decode()
    
    def encrypt(self, data: str) -> str:
        """Encrypt sensitive data."""
        if not self._fernet:
            raise RuntimeError("Secrets manager not initialized")
        
        encrypted_data = self._fernet.encrypt(data.encode())
        return encrypted_data.decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        if not self._fernet:
            raise RuntimeError("Secrets manager not initialized")
        
        decrypted_data = self._fernet.decrypt(encrypted_data.encode())
        return decrypted_data.decode()
    
    def hash_password(self, password: str) -> str:
        """Hash password using HMAC-SHA256."""
        salt = secrets.token_hex(16)
        password_hash = hmac.new(
            salt.encode(),
            password.encode(),
            hashlib.sha256
        ).hexdigest()
        return f"{salt}:{password_hash}"
    
    def verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify password against stored hash."""
        try:
            salt, password_hash = stored_hash.split(':')
            computed_hash = hmac.new(
                salt.encode(),
                password.encode(),
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(password_hash, computed_hash)
        except ValueError:
            return False
    
    def generate_api_key(self) -> str:
        """Generate a secure API key."""
        return secrets.token_urlsafe(32)
    
    def validate_api_key(self, provided_key: str, stored_key_hash: str) -> bool:
        """Validate API key against stored hash."""
        return self.verify_password(provided_key, stored_key_hash)


class SecurityMiddleware:
    """Security middleware for Flask application."""
    
    def __init__(self, app: Flask = None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize security middleware."""
        # Security headers
        @app.after_request
        def add_security_headers(response):
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "connect-src 'self' https://api.coingecko.com https://newsapi.org"
            )
            return response
        
        # Request logging
        @app.before_request
        def log_request_info():
            g.request_start_time = datetime.utcnow()
            g.request_id = secrets.token_hex(8)
            
            logger.info(
                f"Request started: {request.method} {request.path}",
                extra={
                    "request_id": g.request_id,
                    "method": request.method,
                    "path": request.path,
                    "remote_addr": request.remote_addr,
                    "user_agent": request.headers.get('User-Agent', '')
                }
            )
        
        @app.after_request
        def log_response_info(response):
            if hasattr(g, 'request_start_time'):
                duration_ms = (datetime.utcnow() - g.request_start_time).total_seconds() * 1000
                logger.info(
                    f"Request completed: {request.method} {request.path} - {response.status_code}",
                    extra={
                        "request_id": getattr(g, 'request_id', 'unknown'),
                        "status_code": response.status_code,
                        "duration_ms": duration_ms
                    }
                )
            return response
        
        # Global error handler
        @app.errorhandler(429)
        def ratelimit_handler(e):
            return jsonify({
                "error": "Rate limit exceeded",
                "message": str(e.description),
                "retry_after": getattr(e, 'retry_after', None),
                "timestamp": datetime.utcnow().isoformat()
            }), 429
        
        @app.errorhandler(500)
        def internal_error_handler(e):
            logger.error(f"Internal server error: {e}", exc_info=True)
            return jsonify({
                "error": "Internal server error",
                "message": "An unexpected error occurred",
                "timestamp": datetime.utcnow().isoformat()
            }), 500
        
        @app.errorhandler(404)
        def not_found_handler(e):
            return jsonify({
                "error": "Not found",
                "message": "The requested resource was not found",
                "timestamp": datetime.utcnow().isoformat()
            }), 404


class CORSManager:
    """Enhanced CORS management with restrictive configuration."""
    
    def __init__(self, app: Flask = None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize CORS with restrictive configuration."""
        from flask_cors import CORS
        
        # Get allowed origins from environment or use defaults
        allowed_origins = os.environ.get('ALLOWED_ORIGINS', 
                                       'http://localhost:3000,http://localhost:5173').split(',')
        
        # Configure CORS with restrictive settings
        CORS(app,
             origins=allowed_origins,
             methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
             allow_headers=['Content-Type', 'Authorization', 'X-API-Key'],
             expose_headers=['X-RateLimit-Limit', 'X-RateLimit-Remaining', 'X-RateLimit-Reset'],
             supports_credentials=True,
             max_age=3600)  # 1 hour cache for preflight requests


def init_security(app: Flask):
    """Initialize all security components."""
    # Initialize rate limiting
    rate_limiter = RateLimiter(app)
    
    # Initialize secrets management
    secrets_manager = SecretsManager(app)
    
    # Initialize security middleware
    security_middleware = SecurityMiddleware(app)
    
    # Initialize CORS
    cors_manager = CORSManager(app)
    
    # Store instances in app for access
    app.rate_limiter = rate_limiter
    app.secrets_manager = secrets_manager
    app.security_middleware = security_middleware
    app.cors_manager = cors_manager
    
    logger.info("Security components initialized")
    
    return {
        'rate_limiter': rate_limiter,
        'secrets_manager': secrets_manager,
        'security_middleware': security_middleware,
        'cors_manager': cors_manager
    }


# Decorators for common security patterns
def require_api_key(f):
    """Decorator to require valid API key."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({
                "error": "API key required",
                "message": "Please provide an API key in the X-API-Key header",
                "timestamp": datetime.utcnow().isoformat()
            }), 401
        
        # In a real implementation, you would validate against stored keys
        # For now, we'll just check if it's present and has reasonable length
        if len(api_key) < 20:
            return jsonify({
                "error": "Invalid API key",
                "message": "The provided API key is invalid",
                "timestamp": datetime.utcnow().isoformat()
            }), 401
        
        return f(*args, **kwargs)
    return decorated_function


def log_security_event(event_type: str, details: Dict[str, Any] = None):
    """Log security-related events."""
    logger.warning(
        f"Security event: {event_type}",
        extra={
            "event_type": "security",
            "security_event": event_type,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        }
    )
