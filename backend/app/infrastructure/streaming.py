"""
Streaming data processing for real-time market data and predictions.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, AsyncGenerator
from dataclasses import dataclass, asdict
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
import websockets
from websockets.exceptions import ConnectionClosed
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import threading
import queue
import time

from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache
from app.infrastructure.metrics import get_metrics

logger = logging.getLogger(__name__)


@dataclass
class StreamMessage:
    """Base message for streaming data."""
    timestamp: datetime
    message_type: str
    data: Dict[str, Any]
    source: str
    version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StreamMessage':
        """Create from dictionary."""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class MarketDataMessage(StreamMessage):
    """Market data streaming message."""
    asset_symbol: str
    price: float
    volume: float
    high: Optional[float] = None
    low: Optional[float] = None
    open_price: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    
    def __post_init__(self):
        self.message_type = "market_data"


@dataclass
class PredictionMessage(StreamMessage):
    """Prediction streaming message."""
    asset_symbol: str
    prediction: str  # 'BUY', 'SELL', 'HOLD'
    confidence: float
    target_price: Optional[float] = None
    time_horizon: Optional[int] = None  # days
    model_version: Optional[str] = None
    
    def __post_init__(self):
        self.message_type = "prediction"


@dataclass
class NewsMessage(StreamMessage):
    """News streaming message."""
    title: str
    content: str
    source: str
    sentiment: Optional[float] = None
    asset_symbols: Optional[List[str]] = None
    
    def __post_init__(self):
        self.message_type = "news"


class StreamProcessor(LoggerMixin):
    """Base stream processor for handling streaming data."""
    
    def __init__(self, processor_id: str):
        self.processor_id = processor_id
        self.is_running = False
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.processed_count = 0
        self.error_count = 0
    
    async def start(self):
        """Start the stream processor."""
        self.is_running = True
        self.logger.info(f"Starting stream processor: {self.processor_id}")
    
    async def stop(self):
        """Stop the stream processor."""
        self.is_running = False
        self.logger.info(f"Stopping stream processor: {self.processor_id}")
    
    async def process_message(self, message: StreamMessage) -> Optional[StreamMessage]:
        """Process a streaming message."""
        try:
            self.processed_count += 1
            
            # Update metrics
            self.metrics.record_trading_signal(
                signal_type="stream_processed",
                asset_symbol=getattr(message, 'asset_symbol', 'unknown')
            )
            
            return message
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Error processing message: {e}")
            self.metrics.record_error("stream_processing_error", self.processor_id)
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        return {
            "processor_id": self.processor_id,
            "is_running": self.is_running,
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / max(self.processed_count, 1),
        }


class MarketDataProcessor(StreamProcessor):
    """Processor for real-time market data."""
    
    def __init__(self):
        super().__init__("market_data_processor")
        self.price_cache = {}
        self.volume_cache = {}
        self.subscribers = set()
    
    async def process_message(self, message: MarketDataMessage) -> Optional[MarketDataMessage]:
        """Process market data message."""
        message = await super().process_message(message)
        if not message:
            return None
        
        try:
            # Cache latest price
            self.price_cache[message.asset_symbol] = message.price
            self.volume_cache[message.asset_symbol] = message.volume
            
            # Store in Redis cache
            cache_key = f"realtime_price:{message.asset_symbol}"
            self.cache.set(cache_key, {
                "price": message.price,
                "volume": message.volume,
                "timestamp": message.timestamp.isoformat()
            }, ttl=300)  # 5 minutes TTL
            
            # Detect significant price movements
            await self._detect_price_movements(message)
            
            # Notify subscribers
            await self._notify_subscribers(message)
            
            return message
            
        except Exception as e:
            self.logger.error(f"Error processing market data: {e}")
            return None
    
    async def _detect_price_movements(self, message: MarketDataMessage):
        """Detect significant price movements."""
        try:
            # Get previous price from cache
            prev_price = self.price_cache.get(message.asset_symbol)
            if prev_price and message.change_percent:
                # Alert on significant movements (>2%)
                if abs(message.change_percent) > 2.0:
                    alert_message = {
                        "type": "price_alert",
                        "asset_symbol": message.asset_symbol,
                        "change_percent": message.change_percent,
                        "current_price": message.price,
                        "timestamp": message.timestamp.isoformat()
                    }
                    
                    # Store alert in cache
                    alert_key = f"price_alert:{message.asset_symbol}"
                    self.cache.set(alert_key, alert_message, ttl=3600)  # 1 hour TTL
                    
                    self.logger.info(f"Price alert for {message.asset_symbol}: {message.change_percent:.2f}%")
        
        except Exception as e:
            self.logger.error(f"Error detecting price movements: {e}")
    
    async def _notify_subscribers(self, message: MarketDataMessage):
        """Notify subscribers of new market data."""
        try:
            # This would integrate with WebSocket manager
            for subscriber in self.subscribers:
                await subscriber.send_market_data(message)
        except Exception as e:
            self.logger.error(f"Error notifying subscribers: {e}")
    
    def subscribe(self, subscriber):
        """Subscribe to market data updates."""
        self.subscribers.add(subscriber)
    
    def unsubscribe(self, subscriber):
        """Unsubscribe from market data updates."""
        self.subscribers.discard(subscriber)


class PredictionProcessor(StreamProcessor):
    """Processor for real-time predictions."""
    
    def __init__(self):
        super().__init__("prediction_processor")
        self.prediction_cache = {}
        self.confidence_thresholds = {
            'HIGH': 0.8,
            'MEDIUM': 0.6,
            'LOW': 0.4
        }
    
    async def process_message(self, message: PredictionMessage) -> Optional[PredictionMessage]:
        """Process prediction message."""
        message = await super().process_message(message)
        if not message:
            return None
        
        try:
            # Cache latest prediction
            self.prediction_cache[message.asset_symbol] = message
            
            # Store in Redis cache
            cache_key = f"realtime_prediction:{message.asset_symbol}"
            self.cache.set(cache_key, asdict(message), ttl=3600)  # 1 hour TTL
            
            # Detect high-confidence predictions
            await self._detect_high_confidence_predictions(message)
            
            return message
            
        except Exception as e:
            self.logger.error(f"Error processing prediction: {e}")
            return None
    
    async def _detect_high_confidence_predictions(self, message: PredictionMessage):
        """Detect high-confidence predictions for alerts."""
        try:
            if message.confidence >= self.confidence_thresholds['HIGH']:
                alert_message = {
                    "type": "high_confidence_prediction",
                    "asset_symbol": message.asset_symbol,
                    "prediction": message.prediction,
                    "confidence": message.confidence,
                    "target_price": message.target_price,
                    "timestamp": message.timestamp.isoformat()
                }
                
                # Store alert in cache
                alert_key = f"prediction_alert:{message.asset_symbol}"
                self.cache.set(alert_key, alert_message, ttl=3600)  # 1 hour TTL
                
                self.logger.info(f"High confidence prediction for {message.asset_symbol}: {message.prediction} ({message.confidence:.2f})")
        
        except Exception as e:
            self.logger.error(f"Error detecting high confidence predictions: {e}")


class KafkaStreamManager(LoggerMixin):
    """Kafka-based streaming manager."""
    
    def __init__(self, bootstrap_servers: List[str]):
        self.bootstrap_servers = bootstrap_servers
        self.producer = None
        self.consumers = {}
        self.processors = {}
        self.is_running = False
    
    async def start(self):
        """Start Kafka stream manager."""
        try:
            # Initialize producer
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',
                retries=3,
                batch_size=16384,
                linger_ms=10,
                buffer_memory=33554432,
            )
            
            self.is_running = True
            self.logger.info("Kafka stream manager started")
            
        except Exception as e:
            self.logger.error(f"Failed to start Kafka manager: {e}")
            raise
    
    async def stop(self):
        """Stop Kafka stream manager."""
        try:
            if self.producer:
                self.producer.close()
            
            for consumer in self.consumers.values():
                consumer.close()
            
            for processor in self.processors.values():
                await processor.stop()
            
            self.is_running = False
            self.logger.info("Kafka stream manager stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping Kafka manager: {e}")
    
    async def publish_message(self, topic: str, message: StreamMessage, key: str = None):
        """Publish message to Kafka topic."""
        try:
            if not self.producer:
                raise RuntimeError("Kafka producer not initialized")
            
            # Send message
            future = self.producer.send(
                topic=topic,
                value=message.to_dict(),
                key=key or message.asset_symbol if hasattr(message, 'asset_symbol') else None
            )
            
            # Wait for acknowledgment
            record_metadata = future.get(timeout=10)
            
            self.logger.debug(f"Message published to {topic}: {record_metadata.partition}:{record_metadata.offset}")
            
        except Exception as e:
            self.logger.error(f"Failed to publish message to {topic}: {e}")
            raise
    
    async def create_consumer(self, topic: str, group_id: str, processor: StreamProcessor):
        """Create consumer for topic with processor."""
        try:
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=group_id,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                auto_offset_reset='latest',
                enable_auto_commit=True,
                auto_commit_interval_ms=1000,
            )
            
            self.consumers[f"{topic}_{group_id}"] = consumer
            self.processors[f"{topic}_{group_id}"] = processor
            
            # Start consuming in background
            asyncio.create_task(self._consume_messages(consumer, processor))
            
            self.logger.info(f"Created consumer for topic {topic} with group {group_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to create consumer: {e}")
            raise
    
    async def _consume_messages(self, consumer: KafkaConsumer, processor: StreamProcessor):
        """Consume messages from Kafka."""
        try:
            await processor.start()
            
            while self.is_running:
                try:
                    # Poll for messages
                    message_batch = consumer.poll(timeout_ms=1000)
                    
                    for topic_partition, messages in message_batch.items():
                        for message in messages:
                            try:
                                # Convert to StreamMessage
                                if message.value['message_type'] == 'market_data':
                                    stream_message = MarketDataMessage.from_dict(message.value)
                                elif message.value['message_type'] == 'prediction':
                                    stream_message = PredictionMessage.from_dict(message.value)
                                elif message.value['message_type'] == 'news':
                                    stream_message = NewsMessage.from_dict(message.value)
                                else:
                                    stream_message = StreamMessage.from_dict(message.value)
                                
                                # Process message
                                await processor.process_message(stream_message)
                                
                            except Exception as e:
                                self.logger.error(f"Error processing Kafka message: {e}")
                
                except Exception as e:
                    self.logger.error(f"Error in consumer loop: {e}")
                    await asyncio.sleep(1)
            
        except Exception as e:
            self.logger.error(f"Fatal error in consumer: {e}")
        finally:
            await processor.stop()


class WebSocketManager(LoggerMixin):
    """WebSocket manager for real-time client connections."""
    
    def __init__(self):
        self.clients = set()
        self.subscriptions = {}  # client -> set of topics
        self.message_queue = queue.Queue()
        self.is_running = False
    
    async def start(self):
        """Start WebSocket manager."""
        self.is_running = True
        
        # Start message broadcasting thread
        broadcast_thread = threading.Thread(target=self._broadcast_messages, daemon=True)
        broadcast_thread.start()
        
        self.logger.info("WebSocket manager started")
    
    async def stop(self):
        """Stop WebSocket manager."""
        self.is_running = False
        
        # Close all connections
        for client in self.clients:
            try:
                await client.close()
            except Exception:
                pass
        
        self.clients.clear()
        self.subscriptions.clear()
        
        self.logger.info("WebSocket manager stopped")
    
    async def register_client(self, websocket, client_id: str):
        """Register new WebSocket client."""
        self.clients.add(websocket)
        self.subscriptions[websocket] = set()
        
        self.logger.info(f"Client {client_id} connected")
        
        # Send welcome message
        await self.send_to_client(websocket, {
            "type": "connection",
            "status": "connected",
            "client_id": client_id,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def unregister_client(self, websocket, client_id: str):
        """Unregister WebSocket client."""
        self.clients.discard(websocket)
        self.subscriptions.pop(websocket, None)
        
        self.logger.info(f"Client {client_id} disconnected")
    
    async def subscribe(self, websocket, topic: str):
        """Subscribe client to topic."""
        if websocket in self.subscriptions:
            self.subscriptions[websocket].add(topic)
            
            await self.send_to_client(websocket, {
                "type": "subscription",
                "action": "subscribed",
                "topic": topic,
                "timestamp": datetime.utcnow().isoformat()
            })
    
    async def unsubscribe(self, websocket, topic: str):
        """Unsubscribe client from topic."""
        if websocket in self.subscriptions:
            self.subscriptions[websocket].discard(topic)
            
            await self.send_to_client(websocket, {
                "type": "subscription",
                "action": "unsubscribed",
                "topic": topic,
                "timestamp": datetime.utcnow().isoformat()
            })
    
    async def send_to_client(self, websocket, message: Dict[str, Any]):
        """Send message to specific client."""
        try:
            await websocket.send(json.dumps(message))
        except ConnectionClosed:
            # Client disconnected, will be cleaned up later
            pass
        except Exception as e:
            self.logger.error(f"Error sending message to client: {e}")
    
    async def broadcast_to_topic(self, topic: str, message: Dict[str, Any]):
        """Broadcast message to all clients subscribed to topic."""
        # Add to queue for background broadcasting
        self.message_queue.put((topic, message))
    
    def _broadcast_messages(self):
        """Background thread for broadcasting messages."""
        while self.is_running:
            try:
                # Get message from queue
                topic, message = self.message_queue.get(timeout=1)
                
                # Find subscribed clients
                subscribed_clients = [
                    client for client, topics in self.subscriptions.items()
                    if topic in topics
                ]
                
                # Broadcast to subscribed clients
                for client in subscribed_clients:
                    try:
                        # Use asyncio to send message
                        asyncio.run_coroutine_threadsafe(
                            self.send_to_client(client, message),
                            asyncio.new_event_loop()
                        )
                    except Exception as e:
                        self.logger.error(f"Error broadcasting to client: {e}")
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error in broadcast loop: {e}")
    
    async def send_market_data(self, message: MarketDataMessage):
        """Send market data to subscribed clients."""
        await self.broadcast_to_topic("market_data", message.to_dict())
    
    async def send_prediction(self, message: PredictionMessage):
        """Send prediction to subscribed clients."""
        await self.broadcast_to_topic("predictions", message.to_dict())
    
    async def send_alert(self, alert_type: str, alert_data: Dict[str, Any]):
        """Send alert to all clients."""
        alert_message = {
            "type": "alert",
            "alert_type": alert_type,
            "data": alert_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.broadcast_to_topic("alerts", alert_message)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket manager statistics."""
        return {
            "connected_clients": len(self.clients),
            "total_subscriptions": sum(len(topics) for topics in self.subscriptions.values()),
            "is_running": self.is_running,
        }


# Global instances
kafka_manager: Optional[KafkaStreamManager] = None
websocket_manager: Optional[WebSocketManager] = None


async def init_streaming(bootstrap_servers: List[str] = None):
    """Initialize streaming components."""
    global kafka_manager, websocket_manager
    
    # Initialize WebSocket manager
    websocket_manager = WebSocketManager()
    await websocket_manager.start()
    
    # Initialize Kafka manager if servers provided
    if bootstrap_servers:
        kafka_manager = KafkaStreamManager(bootstrap_servers)
        await kafka_manager.start()
        
        # Create processors
        market_processor = MarketDataProcessor()
        prediction_processor = PredictionProcessor()
        
        # Create consumers
        await kafka_manager.create_consumer("market_data", "market_data_group", market_processor)
        await kafka_manager.create_consumer("predictions", "predictions_group", prediction_processor)
    
    logger.info("Streaming components initialized")


def get_kafka_manager() -> Optional[KafkaStreamManager]:
    """Get Kafka manager instance."""
    return kafka_manager


def get_websocket_manager() -> Optional[WebSocketManager]:
    """Get WebSocket manager instance."""
    return websocket_manager


# Utility functions
async def publish_market_data(asset_symbol: str, price: float, volume: float, **kwargs):
    """Publish market data to stream."""
    if kafka_manager:
        message = MarketDataMessage(
            timestamp=datetime.utcnow(),
            asset_symbol=asset_symbol,
            price=price,
            volume=volume,
            source="sentinel_trading",
            data={"asset_symbol": asset_symbol, "price": price, "volume": volume},
            **kwargs
        )
        
        await kafka_manager.publish_message("market_data", message)


async def publish_prediction(asset_symbol: str, prediction: str, confidence: float, **kwargs):
    """Publish prediction to stream."""
    if kafka_manager:
        message = PredictionMessage(
            timestamp=datetime.utcnow(),
            asset_symbol=asset_symbol,
            prediction=prediction,
            confidence=confidence,
            source="sentinel_trading",
            data={"asset_symbol": asset_symbol, "prediction": prediction, "confidence": confidence},
            **kwargs
        )
        
        await kafka_manager.publish_message("predictions", message)
