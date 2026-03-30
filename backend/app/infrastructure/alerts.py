"""
Advanced alert system for price movements and trading events.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import json
import uuid
from collections import defaultdict
import numpy as np
import pandas as pd

from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache
from app.infrastructure.metrics import get_metrics
from app.infrastructure.notifications import get_notification_manager
from app.infrastructure.event_driven_architecture import get_event_bus, EventType

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """Types of alerts."""
    PRICE_MOVEMENT = "price_movement"
    VOLUME_SPIKE = "volume_spike"
    VOLATILITY = "volatility"
    TECHNICAL_INDICATOR = "technical_indicator"
    NEWS_SENTIMENT = "news_sentiment"
    ECONOMIC_EVENT = "economic_event"
    EARNINGS = "earnings"
    PORTFOLIO_RISK = "portfolio_risk"
    SYSTEM_ERROR = "system_error"
    CUSTOM = "custom"


class AlertSeverity(Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status."""
    ACTIVE = "active"
    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISABLED = "disabled"


class ComparisonOperator(Enum):
    """Comparison operators for alert conditions."""
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    EQUAL = "=="
    NOT_EQUAL = "!="
    PERCENT_CHANGE = "percent_change"
    CROSS_ABOVE = "cross_above"
    CROSS_BELOW = "cross_below"


@dataclass
class AlertCondition:
    """Alert condition configuration."""
    metric: str  # e.g., "price", "volume", "rsi"
    operator: ComparisonOperator
    threshold: float
    symbol: Optional[str] = None
    timeframe: Optional[str] = None  # e.g., "1m", "5m", "1h", "1d"
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['operator'] = self.operator.value
        return result


@dataclass
class AlertRule:
    """Alert rule configuration."""
    rule_id: str
    name: str
    description: str
    alert_type: AlertType
    conditions: List[AlertCondition]
    severity: AlertSeverity
    enabled: bool = True
    cooldown_minutes: int = 15  # Minimum time between alerts
    notification_channels: List[str] = None
    user_id: str = "default"
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        if self.notification_channels is None:
            self.notification_channels = ["email", "websocket"]
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['alert_type'] = self.alert_type.value
        result['severity'] = self.severity.value
        result['conditions'] = [condition.to_dict() for condition in self.conditions]
        result['created_at'] = self.created_at.isoformat()
        result['updated_at'] = self.updated_at.isoformat()
        return result


@dataclass
class Alert:
    """Alert instance."""
    alert_id: str
    rule_id: str
    rule_name: str
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    data: Dict[str, Any]
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    status: AlertStatus = AlertStatus.TRIGGERED
    user_id: str = "default"
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['alert_type'] = self.alert_type.value
        result['severity'] = self.severity.value
        result['status'] = self.status.value
        result['triggered_at'] = self.triggered_at.isoformat()
        if self.acknowledged_at:
            result['acknowledged_at'] = self.acknowledged_at.isoformat()
        if self.resolved_at:
            result['resolved_at'] = self.resolved_at.isoformat()
        return result


class AlertEngine(LoggerMixin):
    """Alert processing engine."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.notification_manager = get_notification_manager()
        self.event_bus = get_event_bus()
        
        # Alert rules storage
        self.rules = {}  # rule_id -> AlertRule
        
        # Alert history
        self.alerts = {}  # alert_id -> Alert
        self.alert_history = defaultdict(list)  # rule_id -> List[Alert]
        
        # Cooldown tracking
        self.last_triggered = {}  # rule_id -> datetime
        
        # Market data cache
        self.market_data = {}  # symbol -> DataFrame
        
        # Processing state
        self.processing = False
    
    def create_alert_rule(self, name: str, description: str, alert_type: AlertType,
                         conditions: List[Dict[str, Any]], severity: AlertSeverity,
                         user_id: str = "default", notification_channels: List[str] = None,
                         cooldown_minutes: int = 15) -> str:
        """Create a new alert rule."""
        try:
            rule_id = str(uuid.uuid4())
            
            # Convert condition dictionaries to AlertCondition objects
            condition_objects = []
            for condition_data in conditions:
                condition = AlertCondition(
                    metric=condition_data["metric"],
                    operator=ComparisonOperator(condition_data["operator"]),
                    threshold=condition_data["threshold"],
                    symbol=condition_data.get("symbol"),
                    timeframe=condition_data.get("timeframe")
                )
                condition_objects.append(condition)
            
            # Create alert rule
            rule = AlertRule(
                rule_id=rule_id,
                name=name,
                description=description,
                alert_type=alert_type,
                conditions=condition_objects,
                severity=severity,
                notification_channels=notification_channels,
                user_id=user_id,
                cooldown_minutes=cooldown_minutes
            )
            
            self.rules[rule_id] = rule
            
            self.logger.info(f"Created alert rule {rule_id}: {name}")
            
            # Record metrics
            self.metrics.record_trading_signal(
                signal_type="alert_rule_created",
                asset_symbol=rule_id
            )
            
            return rule_id
            
        except Exception as e:
            self.logger.error(f"Error creating alert rule: {e}")
            raise
    
    def update_alert_rule(self, rule_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing alert rule."""
        try:
            if rule_id not in self.rules:
                return False
            
            rule = self.rules[rule_id]
            
            # Update allowed fields
            if "name" in updates:
                rule.name = updates["name"]
            if "description" in updates:
                rule.description = updates["description"]
            if "severity" in updates:
                rule.severity = AlertSeverity(updates["severity"])
            if "enabled" in updates:
                rule.enabled = updates["enabled"]
            if "notification_channels" in updates:
                rule.notification_channels = updates["notification_channels"]
            if "cooldown_minutes" in updates:
                rule.cooldown_minutes = updates["cooldown_minutes"]
            
            rule.updated_at = datetime.utcnow()
            
            self.logger.info(f"Updated alert rule {rule_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating alert rule: {e}")
            return False
    
    def delete_alert_rule(self, rule_id: str) -> bool:
        """Delete an alert rule."""
        try:
            if rule_id not in self.rules:
                return False
            
            del self.rules[rule_id]
            
            # Clean up cooldown tracking
            if rule_id in self.last_triggered:
                del self.last_triggered[rule_id]
            
            self.logger.info(f"Deleted alert rule {rule_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting alert rule: {e}")
            return False
    
    def get_alert_rules(self, user_id: str = None) -> List[AlertRule]:
        """Get alert rules, optionally filtered by user."""
        try:
            rules = list(self.rules.values())
            
            if user_id:
                rules = [rule for rule in rules if rule.user_id == user_id]
            
            return rules
            
        except Exception as e:
            self.logger.error(f"Error getting alert rules: {e}")
            return []
    
    def get_alerts(self, rule_id: str = None, status: AlertStatus = None,
                   severity: AlertSeverity = None, limit: int = 100) -> List[Alert]:
        """Get alerts with optional filtering."""
        try:
            alerts = list(self.alerts.values())
            
            # Apply filters
            if rule_id:
                alerts = [alert for alert in alerts if alert.rule_id == rule_id]
            
            if status:
                alerts = [alert for alert in alerts if alert.status == status]
            
            if severity:
                alerts = [alert for alert in alerts if alert.severity == severity]
            
            # Sort by triggered_at (newest first)
            alerts.sort(key=lambda x: x.triggered_at, reverse=True)
            
            return alerts[:limit]
            
        except Exception as e:
            self.logger.error(f"Error getting alerts: {e}")
            return []
    
    def acknowledge_alert(self, alert_id: str, user_id: str = None) -> bool:
        """Acknowledge an alert."""
        try:
            if alert_id not in self.alerts:
                return False
            
            alert = self.alerts[alert_id]
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.utcnow()
            
            if user_id:
                alert.user_id = user_id
            
            self.logger.info(f"Acknowledged alert {alert_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error acknowledging alert: {e}")
            return False
    
    def resolve_alert(self, alert_id: str, user_id: str = None) -> bool:
        """Resolve an alert."""
        try:
            if alert_id not in self.alerts:
                return False
            
            alert = self.alerts[alert_id]
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.utcnow()
            
            if user_id:
                alert.user_id = user_id
            
            self.logger.info(f"Resolved alert {alert_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error resolving alert: {e}")
            return False
    
    async def process_market_data(self, symbol: str, price: float, volume: float,
                                timestamp: datetime, additional_data: Dict[str, Any] = None):
        """Process market data and check for alert triggers."""
        try:
            # Update market data cache
            if symbol not in self.market_data:
                self.market_data[symbol] = pd.DataFrame()
            
            # Add new data point
            new_data = {
                'timestamp': timestamp,
                'price': price,
                'volume': volume,
                **(additional_data or {})
            }
            
            self.market_data[symbol] = pd.concat([
                self.market_data[symbol],
                pd.DataFrame([new_data])
            ], ignore_index=True)
            
            # Keep only last 1000 data points
            if len(self.market_data[symbol]) > 1000:
                self.market_data[symbol] = self.market_data[symbol].tail(1000)
            
            # Check alert rules
            await self._check_alert_rules(symbol, price, volume, timestamp, additional_data)
            
        except Exception as e:
            self.logger.error(f"Error processing market data: {e}")
    
    async def _check_alert_rules(self, symbol: str, price: float, volume: float,
                               timestamp: datetime, additional_data: Dict[str, Any]):
        """Check all alert rules for triggers."""
        try:
            for rule in self.rules.values():
                if not rule.enabled:
                    continue
                
                # Check cooldown
                if rule.rule_id in self.last_triggered:
                    time_since_last = timestamp - self.last_triggered[rule.rule_id]
                    if time_since_last.total_seconds() < rule.cooldown_minutes * 60:
                        continue
                
                # Check if rule applies to this symbol
                if rule.conditions and not any(
                    condition.symbol is None or condition.symbol == symbol 
                    for condition in rule.conditions
                ):
                    continue
                
                # Evaluate conditions
                triggered = await self._evaluate_conditions(rule, symbol, price, volume, timestamp, additional_data)
                
                if triggered:
                    await self._trigger_alert(rule, symbol, price, volume, timestamp, additional_data)
                    self.last_triggered[rule.rule_id] = timestamp
            
        except Exception as e:
            self.logger.error(f"Error checking alert rules: {e}")
    
    async def _evaluate_conditions(self, rule: AlertRule, symbol: str, price: float,
                                 volume: float, timestamp: datetime, 
                                 additional_data: Dict[str, Any]) -> bool:
        """Evaluate alert conditions."""
        try:
            for condition in rule.conditions:
                if not await self._evaluate_single_condition(condition, symbol, price, volume, timestamp, additional_data):
                    return False
            
            return True  # All conditions met
            
        except Exception as e:
            self.logger.error(f"Error evaluating conditions: {e}")
            return False
    
    async def _evaluate_single_condition(self, condition: AlertCondition, symbol: str,
                                       price: float, volume: float, timestamp: datetime,
                                       additional_data: Dict[str, Any]) -> bool:
        """Evaluate a single alert condition."""
        try:
            # Get current value for the metric
            current_value = await self._get_metric_value(condition, symbol, price, volume, timestamp, additional_data)
            
            if current_value is None:
                return False
            
            # Get previous value for comparison operators that need it
            previous_value = await self._get_previous_metric_value(condition, symbol, timestamp)
            
            # Evaluate based on operator
            if condition.operator == ComparisonOperator.GREATER_THAN:
                return current_value > condition.threshold
            elif condition.operator == ComparisonOperator.LESS_THAN:
                return current_value < condition.threshold
            elif condition.operator == ComparisonOperator.GREATER_EQUAL:
                return current_value >= condition.threshold
            elif condition.operator == ComparisonOperator.LESS_EQUAL:
                return current_value <= condition.threshold
            elif condition.operator == ComparisonOperator.EQUAL:
                return abs(current_value - condition.threshold) < 1e-6
            elif condition.operator == ComparisonOperator.NOT_EQUAL:
                return abs(current_value - condition.threshold) >= 1e-6
            elif condition.operator == ComparisonOperator.PERCENT_CHANGE:
                if previous_value is None or previous_value == 0:
                    return False
                percent_change = (current_value - previous_value) / abs(previous_value) * 100
                return percent_change > condition.threshold
            elif condition.operator == ComparisonOperator.CROSS_ABOVE:
                if previous_value is None:
                    return False
                return previous_value <= condition.threshold < current_value
            elif condition.operator == ComparisonOperator.CROSS_BELOW:
                if previous_value is None:
                    return False
                return previous_value >= condition.threshold > current_value
            else:
                self.logger.warning(f"Unsupported operator: {condition.operator}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error evaluating condition: {e}")
            return False
    
    async def _get_metric_value(self, condition: AlertCondition, symbol: str,
                              price: float, volume: float, timestamp: datetime,
                              additional_data: Dict[str, Any]) -> Optional[float]:
        """Get current value for a metric."""
        try:
            if condition.metric == "price":
                return price
            elif condition.metric == "volume":
                return volume
            elif condition.metric == "rsi":
                return await self._calculate_rsi(symbol)
            elif condition.metric == "macd":
                return await self._calculate_macd(symbol)
            elif condition.metric == "bollinger_position":
                return await self._calculate_bollinger_position(symbol)
            elif condition.metric == "volume_ratio":
                return await self._calculate_volume_ratio(symbol)
            elif condition.metric == "volatility":
                return await self._calculate_volatility(symbol)
            elif condition.metric == "price_change":
                return await self._calculate_price_change(symbol, price)
            elif condition.metric == "sentiment":
                return await self._get_sentiment_score(symbol)
            else:
                # Check additional data
                if additional_data and condition.metric in additional_data:
                    return additional_data[condition.metric]
                
                self.logger.warning(f"Unknown metric: {condition.metric}")
                return None
            
        except Exception as e:
            self.logger.error(f"Error getting metric value: {e}")
            return None
    
    async def _get_previous_metric_value(self, condition: AlertCondition, symbol: str,
                                       timestamp: datetime) -> Optional[float]:
        """Get previous value for comparison."""
        try:
            if symbol not in self.market_data or len(self.market_data[symbol]) < 2:
                return None
            
            # Get the most recent data point before the current timestamp
            df = self.market_data[symbol]
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Filter to get data before current timestamp
            previous_data = df[df['timestamp'] < timestamp]
            
            if previous_data.empty:
                return None
            
            # Get the most recent previous value
            latest_previous = previous_data.iloc[-1]
            
            if condition.metric == "price":
                return latest_previous['price']
            elif condition.metric == "volume":
                return latest_previous['volume']
            else:
                # For other metrics, we'd need to calculate them on historical data
                # For now, return None
                return None
            
        except Exception as e:
            self.logger.error(f"Error getting previous metric value: {e}")
            return None
    
    async def _calculate_rsi(self, symbol: str, period: int = 14) -> Optional[float]:
        """Calculate RSI for a symbol."""
        try:
            if symbol not in self.market_data or len(self.market_data[symbol]) < period + 1:
                return None
            
            df = self.market_data[symbol].copy()
            
            # Calculate price changes
            df['price_change'] = df['price'].diff()
            
            # Calculate gains and losses
            df['gain'] = df['price_change'].where(df['price_change'] > 0, 0)
            df['loss'] = -df['price_change'].where(df['price_change'] < 0, 0)
            
            # Calculate average gains and losses
            avg_gain = df['gain'].rolling(window=period).mean()
            avg_loss = df['loss'].rolling(window=period).mean()
            
            # Calculate RSI
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi.iloc[-1] if not rsi.empty else None
            
        except Exception as e:
            self.logger.error(f"Error calculating RSI: {e}")
            return None
    
    async def _calculate_macd(self, symbol: str) -> Optional[float]:
        """Calculate MACD for a symbol."""
        try:
            if symbol not in self.market_data or len(self.market_data[symbol]) < 26:
                return None
            
            df = self.market_data[symbol].copy()
            
            # Calculate EMAs
            ema_12 = df['price'].ewm(span=12).mean()
            ema_26 = df['price'].ewm(span=26).mean()
            
            # Calculate MACD line
            macd = ema_12 - ema_26
            
            return macd.iloc[-1] if not macd.empty else None
            
        except Exception as e:
            self.logger.error(f"Error calculating MACD: {e}")
            return None
    
    async def _calculate_bollinger_position(self, symbol: str) -> Optional[float]:
        """Calculate position within Bollinger Bands."""
        try:
            if symbol not in self.market_data or len(self.market_data[symbol]) < 20:
                return None
            
            df = self.market_data[symbol].copy()
            
            # Calculate Bollinger Bands
            sma = df['price'].rolling(window=20).mean()
            std = df['price'].rolling(window=20).std()
            upper_band = sma + (std * 2)
            lower_band = sma - (std * 2)
            
            # Calculate position (0 = lower band, 1 = upper band)
            current_price = df['price'].iloc[-1]
            current_upper = upper_band.iloc[-1]
            current_lower = lower_band.iloc[-1]
            
            if current_upper == current_lower:
                return 0.5
            
            position = (current_price - current_lower) / (current_upper - current_lower)
            return max(0, min(1, position))
            
        except Exception as e:
            self.logger.error(f"Error calculating Bollinger position: {e}")
            return None
    
    async def _calculate_volume_ratio(self, symbol: str) -> Optional[float]:
        """Calculate volume ratio (current / average)."""
        try:
            if symbol not in self.market_data or len(self.market_data[symbol]) < 20:
                return None
            
            df = self.market_data[symbol].copy()
            
            current_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].tail(20).mean()
            
            if avg_volume == 0:
                return None
            
            return current_volume / avg_volume
            
        except Exception as e:
            self.logger.error(f"Error calculating volume ratio: {e}")
            return None
    
    async def _calculate_volatility(self, symbol: str, period: int = 20) -> Optional[float]:
        """Calculate volatility for a symbol."""
        try:
            if symbol not in self.market_data or len(self.market_data[symbol]) < period:
                return None
            
            df = self.market_data[symbol].copy()
            
            # Calculate daily returns
            df['returns'] = df['price'].pct_change()
            
            # Calculate volatility (standard deviation of returns)
            volatility = df['returns'].tail(period).std()
            
            return volatility * np.sqrt(252)  # Annualized volatility
            
        except Exception as e:
            self.logger.error(f"Error calculating volatility: {e}")
            return None
    
    async def _calculate_price_change(self, symbol: str, current_price: float, period: int = 1) -> Optional[float]:
        """Calculate price change over a period."""
        try:
            if symbol not in self.market_data or len(self.market_data[symbol]) < period + 1:
                return None
            
            df = self.market_data[symbol].copy()
            
            # Get price from 'period' periods ago
            if len(df) < period + 1:
                return None
            
            previous_price = df['price'].iloc[-(period + 1)]
            
            if previous_price == 0:
                return None
            
            return (current_price - previous_price) / previous_price * 100
            
        except Exception as e:
            self.logger.error(f"Error calculating price change: {e}")
            return None
    
    async def _get_sentiment_score(self, symbol: str) -> Optional[float]:
        """Get sentiment score for a symbol."""
        try:
            # Mock implementation - in production, integrate with sentiment service
            return np.random.uniform(-1, 1)
            
        except Exception as e:
            self.logger.error(f"Error getting sentiment score: {e}")
            return None
    
    async def _trigger_alert(self, rule: AlertRule, symbol: str, price: float, volume: float,
                           timestamp: datetime, additional_data: Dict[str, Any]):
        """Trigger an alert."""
        try:
            # Create alert
            alert_id = str(uuid.uuid4())
            
            # Generate alert message
            message = self._generate_alert_message(rule, symbol, price, volume, additional_data)
            
            alert = Alert(
                alert_id=alert_id,
                rule_id=rule.rule_id,
                rule_name=rule.name,
                alert_type=rule.alert_type,
                severity=rule.severity,
                message=message,
                data={
                    "symbol": symbol,
                    "price": price,
                    "volume": volume,
                    "timestamp": timestamp.isoformat(),
                    **additional_data
                },
                triggered_at=timestamp,
                user_id=rule.user_id
            )
            
            # Store alert
            self.alerts[alert_id] = alert
            self.alert_history[rule.rule_id].append(alert)
            
            # Send notifications
            await self._send_alert_notifications(alert, rule)
            
            # Publish event
            await self.event_bus.publish_event(
                EventType.SYSTEM_ERROR,  # Using existing event type
                {
                    "alert_id": alert_id,
                    "rule_id": rule.rule_id,
                    "alert_type": rule.alert_type.value,
                    "severity": rule.severity.value,
                    "symbol": symbol,
                    "message": message
                },
                source="alert_engine",
                priority="high" if rule.severity in [AlertSeverity.HIGH, AlertSeverity.CRITICAL] else "normal"
            )
            
            self.logger.info(f"Triggered alert {alert_id} for rule {rule.rule_id}")
            
            # Record metrics
            self.metrics.record_trading_signal(
                signal_type="alert_triggered",
                asset_symbol=rule.alert_type.value
            )
            
        except Exception as e:
            self.logger.error(f"Error triggering alert: {e}")
    
    def _generate_alert_message(self, rule: AlertRule, symbol: str, price: float,
                             volume: float, additional_data: Dict[str, Any]) -> str:
        """Generate alert message."""
        try:
            conditions_str = " AND ".join([
                f"{condition.metric} {condition.operator.value} {condition.threshold}"
                for condition in rule.conditions
            ])
            
            message = f"Alert: {rule.name} triggered for {symbol}. "
            message += f"Conditions: {conditions_str}. "
            message += f"Current price: ${price:.2f}, Volume: {volume:,.0f}"
            
            return message
            
        except Exception as e:
            self.logger.error(f"Error generating alert message: {e}")
            return f"Alert triggered for {symbol}"
    
    async def _send_alert_notifications(self, alert: Alert, rule: AlertRule):
        """Send notifications for an alert."""
        try:
            for channel in rule.notification_channels:
                if channel == "email":
                    await self.notification_manager.send_system_alert(
                        alert.message,
                        alert.severity.value,
                        alert_id=alert.alert_id,
                        rule_name=rule.rule_name,
                        symbol=alert.data.get("symbol")
                    )
                elif channel == "websocket":
                    await self.notification_manager.send_system_alert(
                        alert.message,
                        alert.severity.value,
                        alert_id=alert.alert_id,
                        rule_name=rule.rule_name,
                        symbol=alert.data.get("symbol")
                    )
                elif channel == "webhook":
                    # Implement webhook notification
                    pass
            
        except Exception as e:
            self.logger.error(f"Error sending alert notifications: {e}")
    
    def get_alert_statistics(self, user_id: str = None) -> Dict[str, Any]:
        """Get alert statistics."""
        try:
            alerts = list(self.alerts.values())
            
            if user_id:
                alerts = [alert for alert in alerts if alert.user_id == user_id]
            
            if not alerts:
                return {"total_alerts": 0}
            
            # Calculate statistics
            total_alerts = len(alerts)
            
            alerts_by_severity = {}
            for severity in AlertSeverity:
                count = len([alert for alert in alerts if alert.severity == severity])
                alerts_by_severity[severity.value] = count
            
            alerts_by_type = {}
            for alert_type in AlertType:
                count = len([alert for alert in alerts if alert.alert_type == alert_type])
                alerts_by_type[alert_type.value] = count
            
            alerts_by_status = {}
            for status in AlertStatus:
                count = len([alert for alert in alerts if alert.status == status])
                alerts_by_status[status.value] = count
            
            # Recent alerts (last 24 hours)
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)
            recent_alerts = len([alert for alert in alerts if alert.triggered_at >= recent_cutoff])
            
            # Most active rules
            rule_counts = {}
            for alert in alerts:
                rule_counts[alert.rule_id] = rule_counts.get(alert.rule_id, 0) + 1
            
            most_active_rules = sorted(rule_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            
            return {
                "total_alerts": total_alerts,
                "recent_alerts_24h": recent_alerts,
                "alerts_by_severity": alerts_by_severity,
                "alerts_by_type": alerts_by_type,
                "alerts_by_status": alerts_by_status,
                "most_active_rules": [
                    {"rule_id": rule_id, "count": count}
                    for rule_id, count in most_active_rules
                ],
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting alert statistics: {e}")
            return {"error": str(e)}


# Global instance
alert_engine = AlertEngine()


def get_alert_engine() -> AlertEngine:
    """Get alert engine instance."""
    return alert_engine


# Utility functions
def create_price_alert(symbol: str, threshold: float, operator: str = ">", 
                      severity: str = "medium", user_id: str = "default") -> str:
    """Create a simple price alert."""
    try:
        conditions = [{
            "metric": "price",
            "operator": operator,
            "threshold": threshold,
            "symbol": symbol
        }]
        
        return alert_engine.create_alert_rule(
            name=f"Price Alert - {symbol}",
            description=f"Alert when {symbol} price goes {operator} ${threshold}",
            alert_type=AlertType.PRICE_MOVEMENT,
            conditions=conditions,
            severity=AlertSeverity(severity),
            user_id=user_id
        )
        
    except Exception as e:
        logger.error(f"Error creating price alert: {e}")
        raise


def create_volume_alert(symbol: str, threshold: float, operator: str = ">", 
                        severity: str = "medium", user_id: str = "default") -> str:
    """Create a volume spike alert."""
    try:
        conditions = [{
            "metric": "volume_ratio",
            "operator": operator,
            "threshold": threshold,
            "symbol": symbol
        }]
        
        return alert_engine.create_alert_rule(
            name=f"Volume Alert - {symbol}",
            description=f"Alert when {symbol} volume ratio goes {operator} {threshold}x",
            alert_type=AlertType.VOLUME_SPIKE,
            conditions=conditions,
            severity=AlertSeverity(severity),
            user_id=user_id
        )
        
    except Exception as e:
        logger.error(f"Error creating volume alert: {e}")
        raise


def create_rsi_alert(symbol: str, threshold: float, operator: str = "<", 
                     severity: str = "medium", user_id: str = "default") -> str:
    """Create an RSI alert."""
    try:
        conditions = [{
            "metric": "rsi",
            "operator": operator,
            "threshold": threshold,
            "symbol": symbol
        }]
        
        return alert_engine.create_alert_rule(
            name=f"RSI Alert - {symbol}",
            description=f"Alert when {symbol} RSI goes {operator} {threshold}",
            alert_type=AlertType.TECHNICAL_INDICATOR,
            conditions=conditions,
            severity=AlertSeverity(severity),
            user_id=user_id
        )
        
    except Exception as e:
        logger.error(f"Error creating RSI alert: {e}")
        raise


# Event handlers
async def handle_market_data_event(event):
    """Handle market data events for alert processing."""
    try:
        data = event.payload
        symbol = data.get("symbol")
        price = data.get("price")
        volume = data.get("volume")
        timestamp = datetime.fromisoformat(data.get("timestamp"))
        
        if symbol and price and volume:
            await alert_engine.process_market_data(symbol, price, volume, timestamp, data)
        
    except Exception as e:
        logger.error(f"Error handling market data event: {e}")


# Register event handler
event_bus = get_event_bus()
event_bus.register_handler(EventType.MARKET_DATA_RECEIVED, handle_market_data_event)
