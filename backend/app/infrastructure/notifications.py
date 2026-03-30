"""
Notification system for Sentinel Trading with multiple channels.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import json
import requests
from jinja2 import Template

from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache
from app.infrastructure.metrics import get_metrics
from app.api.websocket import broadcast_system_alert

logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """Notification channels."""
    WEBSOCKET = "websocket"
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    PUSH = "push"


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationType(Enum):
    """Notification types."""
    PRICE_ALERT = "price_alert"
    PREDICTION_ALERT = "prediction_alert"
    SYSTEM_ALERT = "system_alert"
    DATA_QUALITY_ALERT = "data_quality_alert"
    PERFORMANCE_ALERT = "performance_alert"
    ERROR_ALERT = "error_alert"
    SUCCESS_ALERT = "success_alert"


@dataclass
class NotificationMessage:
    """Notification message structure."""
    id: str
    type: NotificationType
    priority: NotificationPriority
    title: str
    message: str
    data: Dict[str, Any]
    channels: List[NotificationChannel]
    recipients: List[str]
    created_at: datetime
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result['type'] = self.type.value
        result['priority'] = self.priority.value
        result['channels'] = [c.value for c in self.channels]
        result['created_at'] = self.created_at.isoformat()
        if self.expires_at:
            result['expires_at'] = self.expires_at.isoformat()
        return result


class NotificationChannelHandler(LoggerMixin):
    """Base class for notification channel handlers."""
    
    def __init__(self, channel: NotificationChannel):
        self.channel = channel
        self.metrics = get_metrics()
        self.cache = get_cache()
    
    async def send(self, notification: NotificationMessage) -> bool:
        """Send notification through this channel."""
        raise NotImplementedError
    
    def is_enabled(self) -> bool:
        """Check if channel is enabled."""
        return True


class WebSocketNotificationHandler(NotificationChannelHandler):
    """WebSocket notification handler."""
    
    def __init__(self):
        super().__init__(NotificationChannel.WEBSOCKET)
    
    async def send(self, notification: NotificationMessage) -> bool:
        """Send notification via WebSocket."""
        try:
            # Broadcast to WebSocket clients
            broadcast_system_alert(
                message=notification.message,
                severity=notification.priority.value
            )
            
            self.logger.info(f"WebSocket notification sent: {notification.title}")
            
            # Record metrics
            self.metrics.record_trading_signal(
                signal_type="websocket_notification_sent",
                asset_symbol=notification.type.value
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending WebSocket notification: {e}")
            return False


class EmailNotificationHandler(NotificationChannelHandler):
    """Email notification handler."""
    
    def __init__(self, smtp_host: str = None, smtp_port: int = None, 
                 smtp_user: str = None, smtp_password: str = None):
        super().__init__(NotificationChannel.EMAIL)
        self.smtp_host = smtp_host or os.environ.get('SMTP_HOST', 'localhost')
        self.smtp_port = smtp_port or int(os.environ.get('SMTP_PORT', '587'))
        self.smtp_user = smtp_user or os.environ.get('SMTP_USER')
        self.smtp_password = smtp_password or os.environ.get('SMTP_PASSWORD')
        self.from_email = os.environ.get('FROM_EMAIL', 'noreply@sentineltrading.com')
    
    async def send(self, notification: NotificationMessage) -> bool:
        """Send notification via email."""
        try:
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = ', '.join(notification.recipients)
            msg['Subject'] = notification.title
            
            # Create HTML body
            html_body = self._create_email_html(notification)
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.smtp_user and self.smtp_password:
                    server.starttls()
                    server.login(self.smtp_user, self.smtp_password)
                
                server.send_message(msg)
            
            self.logger.info(f"Email notification sent to {len(notification.recipients)} recipients")
            
            # Record metrics
            self.metrics.record_trading_signal(
                signal_type="email_notification_sent",
                asset_symbol=notification.type.value
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending email notification: {e}")
            return False
    
    def _create_email_html(self, notification: NotificationMessage) -> str:
        """Create HTML email body."""
        template = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{{ title }}</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
                .container { max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                .header { text-align: center; margin-bottom: 30px; }
                .logo { font-size: 24px; font-weight: bold; color: #2563eb; }
                .content { margin-bottom: 30px; }
                .priority { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; text-transform: uppercase; }
                .priority.low { background-color: #10b981; color: white; }
                .priority.medium { background-color: #f59e0b; color: white; }
                .priority.high { background-color: #ef4444; color: white; }
                .priority.critical { background-color: #dc2626; color: white; }
                .footer { text-align: center; color: #666; font-size: 12px; margin-top: 30px; }
                .data-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                .data-table th, .data-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                .data-table th { background-color: #f8f9fa; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">Sentinel Trading</div>
                </div>
                
                <div class="content">
                    <h2>{{ title }}</h2>
                    <span class="priority {{ priority }}">{{ priority }}</span>
                    <p>{{ message }}</p>
                    
                    {% if data %}
                    <h3>Details:</h3>
                    <table class="data-table">
                        {% for key, value in data.items() %}
                        <tr>
                            <th>{{ key.replace('_', ' ').title() }}</th>
                            <td>{{ value }}</td>
                        </tr>
                        {% endfor %}
                    </table>
                    {% endif %}
                </div>
                
                <div class="footer">
                    <p>This notification was sent by Sentinel Trading at {{ created_at }}</p>
                    <p>If you no longer wish to receive these notifications, please update your preferences.</p>
                </div>
            </div>
        </body>
        </html>
        """)
        
        return template.render(
            title=notification.title,
            message=notification.message,
            priority=notification.priority.value,
            data=notification.data,
            created_at=notification.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
        )


class WebhookNotificationHandler(NotificationChannelHandler):
    """Webhook notification handler."""
    
    def __init__(self, webhook_urls: Dict[str, str] = None):
        super().__init__(NotificationChannel.WEBHOOK)
        self.webhook_urls = webhook_urls or {}
        self.timeout = 30  # seconds
    
    async def send(self, notification: NotificationMessage) -> bool:
        """Send notification via webhook."""
        try:
            # Get webhook URL for notification type
            webhook_url = self.webhook_urls.get(notification.type.value)
            if not webhook_url:
                self.logger.warning(f"No webhook URL configured for notification type: {notification.type.value}")
                return False
            
            # Prepare payload
            payload = {
                "id": notification.id,
                "type": notification.type.value,
                "priority": notification.priority.value,
                "title": notification.title,
                "message": notification.message,
                "data": notification.data,
                "recipients": notification.recipients,
                "created_at": notification.created_at.isoformat(),
                "metadata": notification.metadata or {}
            }
            
            # Send webhook
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
            
            response.raise_for_status()
            
            self.logger.info(f"Webhook notification sent: {notification.title}")
            
            # Record metrics
            self.metrics.record_trading_signal(
                signal_type="webhook_notification_sent",
                asset_symbol=notification.type.value
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending webhook notification: {e}")
            return False


class NotificationManager(LoggerMixin):
    """Main notification manager."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.handlers = {}
        self.notification_history = []  # In-memory history (in production, use database)
        self.max_history = 1000
        
        # Initialize handlers
        self._initialize_handlers()
    
    def _initialize_handlers(self):
        """Initialize notification channel handlers."""
        self.handlers[NotificationChannel.WEBSOCKET] = WebSocketNotificationHandler()
        self.handlers[NotificationChannel.EMAIL] = EmailNotificationHandler()
        self.handlers[NotificationChannel.WEBHOOK] = WebhookNotificationHandler()
    
    async def send_notification(self, notification: NotificationMessage) -> Dict[str, bool]:
        """Send notification through all configured channels."""
        results = {}
        
        for channel in notification.channels:
            if channel in self.handlers:
                handler = self.handlers[channel]
                
                if handler.is_enabled():
                    try:
                        success = await handler.send(notification)
                        results[channel.value] = success
                        
                        if success:
                            self.logger.info(f"Notification sent via {channel.value}: {notification.title}")
                        else:
                            self.logger.error(f"Failed to send notification via {channel.value}: {notification.title}")
                    
                    except Exception as e:
                        self.logger.error(f"Error sending notification via {channel.value}: {e}")
                        results[channel.value] = False
                else:
                    results[channel.value] = False
                    self.logger.warning(f"Channel {channel.value} is disabled")
            else:
                results[channel.value] = False
                self.logger.warning(f"No handler configured for channel: {channel.value}")
        
        # Add to history
        self._add_to_history(notification, results)
        
        # Cache notification
        cache_key = f"notification:{notification.id}"
        self.cache.set(cache_key, {
            "notification": notification.to_dict(),
            "results": results,
            "sent_at": datetime.utcnow().isoformat()
        }, ttl=86400)  # 24 hours TTL
        
        # Record metrics
        success_count = sum(1 for success in results.values() if success)
        self.metrics.record_trading_signal(
            signal_type="notification_sent",
            asset_symbol=f"{success_count}/{len(results)}_channels"
        )
        
        return results
    
    def _add_to_history(self, notification: NotificationMessage, results: Dict[str, bool]):
        """Add notification to history."""
        history_entry = {
            "notification": notification.to_dict(),
            "results": results,
            "sent_at": datetime.utcnow().isoformat()
        }
        
        self.notification_history.append(history_entry)
        
        # Limit history size
        if len(self.notification_history) > self.max_history:
            self.notification_history = self.notification_history[-self.max_history:]
    
    def create_notification(self, 
                          type: NotificationType,
                          priority: NotificationPriority,
                          title: str,
                          message: str,
                          data: Dict[str, Any] = None,
                          channels: List[NotificationChannel] = None,
                          recipients: List[str] = None,
                          expires_in_hours: int = None) -> NotificationMessage:
        """Create a notification message."""
        import uuid
        
        notification_id = str(uuid.uuid4())
        created_at = datetime.utcnow()
        
        expires_at = None
        if expires_in_hours:
            expires_at = created_at + timedelta(hours=expires_in_hours)
        
        # Default channels
        if channels is None:
            channels = [NotificationChannel.WEBSOCKET]
        
        # Default recipients
        if recipients is None:
            recipients = ["all"]
        
        return NotificationMessage(
            id=notification_id,
            type=type,
            priority=priority,
            title=title,
            message=message,
            data=data or {},
            channels=channels,
            recipients=recipients,
            created_at=created_at,
            expires_at=expires_at
        )
    
    async def send_price_alert(self, asset_symbol: str, price: float, change_percent: float, **kwargs):
        """Send price alert notification."""
        notification = self.create_notification(
            type=NotificationType.PRICE_ALERT,
            priority=NotificationPriority.MEDIUM if abs(change_percent) < 5 else NotificationPriority.HIGH,
            title=f"Price Alert: {asset_symbol}",
            message=f"Significant price movement for {asset_symbol}: {change_percent:.2f}% (Current: ${price:.2f})",
            data={
                "asset_symbol": asset_symbol,
                "current_price": price,
                "change_percent": change_percent,
                **kwargs
            },
            channels=[NotificationChannel.WEBSOCKET, NotificationChannel.EMAIL],
            recipients=["traders"]
        )
        
        return await self.send_notification(notification)
    
    async def send_prediction_alert(self, asset_symbol: str, prediction: str, confidence: float, **kwargs):
        """Send prediction alert notification."""
        notification = self.create_notification(
            type=NotificationType.PREDICTION_ALERT,
            priority=NotificationPriority.HIGH if confidence >= 0.8 else NotificationPriority.MEDIUM,
            title=f"Prediction Alert: {asset_symbol}",
            message=f"High confidence prediction for {asset_symbol}: {prediction} ({confidence:.2f})",
            data={
                "asset_symbol": asset_symbol,
                "prediction": prediction,
                "confidence": confidence,
                **kwargs
            },
            channels=[NotificationChannel.WEBSOCKET, NotificationChannel.EMAIL],
            recipients=["analysts"]
        )
        
        return await self.send_notification(notification)
    
    async def send_system_alert(self, message: str, severity: str = "info", **kwargs):
        """Send system alert notification."""
        priority_map = {
            "info": NotificationPriority.LOW,
            "warning": NotificationPriority.MEDIUM,
            "error": NotificationPriority.HIGH,
            "critical": NotificationPriority.CRITICAL
        }
        
        priority = priority_map.get(severity, NotificationPriority.MEDIUM)
        
        notification = self.create_notification(
            type=NotificationType.SYSTEM_ALERT,
            priority=priority,
            title=f"System Alert: {severity.title()}",
            message=message,
            data={
                "severity": severity,
                **kwargs
            },
            channels=[NotificationChannel.WEBSOCKET, NotificationChannel.EMAIL],
            recipients=["admins"]
        )
        
        return await self.send_notification(notification)
    
    async def send_data_quality_alert(self, dataset: str, quality_level: str, issues: List[str], **kwargs):
        """Send data quality alert."""
        notification = self.create_notification(
            type=NotificationType.DATA_QUALITY_ALERT,
            priority=NotificationPriority.MEDIUM if quality_level in ["excellent", "good"] else NotificationPriority.HIGH,
            title=f"Data Quality Alert: {dataset}",
            message=f"Data quality issue detected for {dataset}: {quality_level}",
            data={
                "dataset": dataset,
                "quality_level": quality_level,
                "issues": issues,
                **kwargs
            },
            channels=[NotificationChannel.WEBSOCKET, NotificationChannel.EMAIL],
            recipients=["data_team"]
        )
        
        return await self.send_notification(notification)
    
    async def send_error_alert(self, component: str, error: str, **kwargs):
        """Send error alert notification."""
        notification = self.create_notification(
            type=NotificationType.ERROR_ALERT,
            priority=NotificationPriority.HIGH,
            title=f"Error Alert: {component}",
            message=f"Error detected in {component}: {error}",
            data={
                "component": component,
                "error": error,
                **kwargs
            },
            channels=[NotificationChannel.WEBSOCKET, NotificationChannel.EMAIL, NotificationChannel.WEBHOOK],
            recipients=["devops", "developers"]
        )
        
        return await self.send_notification(notification)
    
    async def send_success_alert(self, operation: str, details: str, **kwargs):
        """Send success notification."""
        notification = self.create_notification(
            type=NotificationType.SUCCESS_ALERT,
            priority=NotificationPriority.LOW,
            title=f"Success: {operation}",
            message=f"Operation completed successfully: {operation} - {details}",
            data={
                "operation": operation,
                "details": details,
                **kwargs
            },
            channels=[NotificationChannel.WEBSOCKET],
            recipients=["all"]
        )
        
        return await self.send_notification(notification)
    
    def get_notification_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get notification history."""
        return self.notification_history[-limit:]
    
    def get_notification_stats(self) -> Dict[str, Any]:
        """Get notification statistics."""
        if not self.notification_history:
            return {
                "total_notifications": 0,
                "success_rate": 0.0,
                "by_type": {},
                "by_priority": {},
                "by_channel": {}
            }
        
        total_notifications = len(self.notification_history)
        successful_notifications = 0
        
        type_counts = {}
        priority_counts = {}
        channel_counts = {}
        
        for entry in self.notification_history:
            notification = entry["notification"]
            results = entry["results"]
            
            # Count by type
            notification_type = notification["type"]
            type_counts[notification_type] = type_counts.get(notification_type, 0) + 1
            
            # Count by priority
            priority = notification["priority"]
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
            
            # Count successful channels
            for channel, success in results.items():
                if success:
                    successful_notifications += 1
                    channel_counts[channel] = channel_counts.get(channel, 0) + 1
        
        success_rate = successful_notifications / (total_notifications * len(self.handlers)) if total_notifications > 0 else 0
        
        return {
            "total_notifications": total_notifications,
            "successful_notifications": successful_notifications,
            "success_rate": success_rate,
            "by_type": type_counts,
            "by_priority": priority_counts,
            "by_channel": channel_counts,
            "active_handlers": list(self.handlers.keys())
        }


# Global notification manager instance
notification_manager = NotificationManager()


def get_notification_manager() -> NotificationManager:
    """Get notification manager instance."""
    return notification_manager


# Utility functions for common notifications
async def send_price_alert(asset_symbol: str, price: float, change_percent: float, **kwargs):
    """Send price alert."""
    return await notification_manager.send_price_alert(asset_symbol, price, change_percent, **kwargs)


async def send_prediction_alert(asset_symbol: str, prediction: str, confidence: float, **kwargs):
    """Send prediction alert."""
    return await notification_manager.send_prediction_alert(asset_symbol, prediction, confidence, **kwargs)


async def send_system_alert(message: str, severity: str = "info", **kwargs):
    """Send system alert."""
    return await notification_manager.send_system_alert(message, severity, **kwargs)


async def send_error_alert(component: str, error: str, **kwargs):
    """Send error alert."""
    return await notification_manager.send_error_alert(component, error, **kwargs)


async def send_success_alert(operation: str, details: str, **kwargs):
    """Send success alert."""
    return await notification_manager.send_success_alert(operation, details, **kwargs)


# Notification decorators
def notify_on_success(operation: str, message: str = None):
    """Decorator to send success notification on function completion."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                
                details = message or f"{operation} completed successfully"
                await send_success_alert(operation, details)
                
                return result
            except Exception as e:
                await send_error_alert(operation, str(e))
                raise
        
        def sync_wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                
                details = message or f"{operation} completed successfully"
                # In sync context, we can't await, so we'll create a task
                import asyncio
                asyncio.create_task(send_success_alert(operation, details))
                
                return result
            except Exception as e:
                asyncio.create_task(send_error_alert(operation, str(e)))
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def notify_on_error(component: str):
    """Decorator to send error notification on function failure."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                await send_error_alert(component, str(e))
                raise
        
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                import asyncio
                asyncio.create_task(send_error_alert(component, str(e)))
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator
