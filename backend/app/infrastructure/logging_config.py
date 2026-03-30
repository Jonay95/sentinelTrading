"""
Structured logging configuration for Sentinel Trading.
"""

import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
import json

from app.config import Config


class StructuredFormatter(logging.Formatter):
    """Structured JSON formatter for consistent log formatting."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                'filename', 'module', 'lineno', 'funcName', 'created',
                'msecs', 'relativeCreated', 'thread', 'threadName',
                'processName', 'process', 'getMessage', 'exc_info',
                'exc_text', 'stack_info'
            }:
                log_entry[key] = value
        
        return json.dumps(log_entry, default=str)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output during development."""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        
        # Build formatted message
        formatted = (
            f"{color}[{timestamp}] {record.levelname:8} "
            f"{record.name}:{record.lineno} - {record.getMessage()}{reset}"
        )
        
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"
        
        return formatted


def setup_logging(config: Config = None) -> None:
    """Setup structured logging configuration."""
    if config is None:
        # Default configuration for development
        log_level = logging.INFO
        log_format = "colored"
        log_file = None
    else:
        log_level = getattr(logging, getattr(config, 'LOG_LEVEL', 'INFO').upper())
        log_format = getattr(config, 'LOG_FORMAT', 'colored')
        log_file = getattr(config, 'LOG_FILE', None)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    if log_format == 'json':
        console_formatter = StructuredFormatter()
    else:  # colored format for development
        console_formatter = ColoredFormatter()
    
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if configured)
    if log_file:
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(file_handler)
    
    # Configure specific loggers
    configure_specific_loggers()


def configure_specific_loggers() -> None:
    """Configure logging levels for specific modules."""
    # External API loggers
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('yfinance').setLevel(logging.WARNING)
    
    # Application loggers
    logging.getLogger('app.infrastructure.resilience').setLevel(logging.INFO)
    logging.getLogger('app.application.use_cases').setLevel(logging.INFO)
    
    # Database logger
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)


class LoggerMixin:
    """Mixin class to add structured logging capabilities."""
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger for the current class."""
        if not hasattr(self, '_logger'):
            self._logger = logging.getLogger(self.__class__.__module__ + '.' + self.__class__.__name__)
        return self._logger
    
    def log_api_call(self, api_name: str, endpoint: str, 
                    duration_ms: float = None, status: str = None, 
                    error: str = None, **extra_fields):
        """Log API call with structured information."""
        log_data = {
            "event_type": "api_call",
            "api_name": api_name,
            "endpoint": endpoint,
            "duration_ms": duration_ms,
            "status": status,
            "error": error,
            **extra_fields
        }
        
        if error:
            self.logger.error(f"API call failed: {api_name} - {endpoint}", extra=log_data)
        else:
            self.logger.info(f"API call: {api_name} - {endpoint}", extra=log_data)
    
    def log_business_event(self, event_type: str, asset_id: int = None, 
                          asset_symbol: str = None, **extra_fields):
        """Log business events with structured information."""
        log_data = {
            "event_type": event_type,
            "asset_id": asset_id,
            "asset_symbol": asset_symbol,
            **extra_fields
        }
        
        self.logger.info(f"Business event: {event_type}", extra=log_data)
    
    def log_prediction_event(self, asset_symbol: str, prediction_value: float, 
                           confidence: float, signal: str, **extra_fields):
        """Log prediction events with structured information."""
        log_data = {
            "event_type": "prediction",
            "asset_symbol": asset_symbol,
            "prediction_value": prediction_value,
            "confidence": confidence,
            "signal": signal,
            **extra_fields
        }
        
        self.logger.info(f"Prediction generated for {asset_symbol}", extra=log_data)
    
    def log_error_with_context(self, error: Exception, context: Dict[str, Any] = None):
        """Log errors with additional context."""
        log_data = {
            "event_type": "error",
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context or {}
        }
        
        self.logger.error(f"Error occurred: {type(error).__name__}", extra=log_data, exc_info=True)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name."""
    return logging.getLogger(name)


# Context manager for timing operations
class LogTimer:
    """Context manager for timing operations and logging duration."""
    
    def __init__(self, logger: logging.Logger, operation: str, **extra_fields):
        self.logger = logger
        self.operation = operation
        self.extra_fields = extra_fields
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.utcnow()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (datetime.utcnow() - self.start_time).total_seconds() * 1000
        
        log_data = {
            "event_type": "operation_timing",
            "operation": self.operation,
            "duration_ms": duration_ms,
            **self.extra_fields
        }
        
        if exc_type:
            log_data["error"] = str(exc_val)
            self.logger.error(f"Operation failed: {self.operation}", extra=log_data)
        else:
            self.logger.info(f"Operation completed: {self.operation}", extra=log_data)


def log_timing(logger: logging.Logger, operation: str, **extra_fields):
    """Decorator to log function execution time."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with LogTimer(logger, operation, **extra_fields):
                return func(*args, **kwargs)
        return wrapper
    return decorator


# Initialize logging when module is imported
if not logging.getLogger().handlers:
    setup_logging()
