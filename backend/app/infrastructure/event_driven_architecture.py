"""
Event-driven architecture design for Sentinel Trading microservices.
"""

import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
import uuid
import weakref
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import threading

from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache
from app.infrastructure.metrics import get_metrics
from app.infrastructure.streaming import get_kafka_manager, StreamMessage

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Event types in the system."""
    MARKET_DATA_RECEIVED = "market_data_received"
    PREDICTION_GENERATED = "prediction_generated"
    TRADE_EXECUTED = "trade_executed"
    PORTFOLIO_UPDATED = "portfolio_updated"
    RISK_ALERT = "risk_alert"
    MODEL_TRAINED = "model_trained"
    DATA_QUALITY_ISSUE = "data_quality_issue"
    SYSTEM_ERROR = "system_error"
    USER_ACTION = "user_action"
    SCHEDULED_TASK = "scheduled_task"


class EventPriority(Enum):
    """Event priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class EventStatus(Enum):
    """Event processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class Event:
    """Event data structure."""
    event_id: str
    event_type: EventType
    priority: EventPriority
    payload: Dict[str, Any]
    timestamp: datetime
    source: str
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    status: EventStatus = EventStatus.PENDING
    processing_time: Optional[float] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['event_type'] = self.event_type.value
        result['priority'] = self.priority.value
        result['timestamp'] = self.timestamp.isoformat()
        result['status'] = self.status.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create Event from dictionary."""
        data['event_type'] = EventType(data['event_type'])
        data['priority'] = EventPriority(data['priority'])
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        data['status'] = EventStatus(data.get('status', 'pending'))
        return cls(**data)


@dataclass
class EventHandler:
    """Event handler configuration."""
    handler_id: str
    event_type: EventType
    handler_func: Callable
    async_handler: bool = False
    retry_on_failure: bool = True
    max_retries: int = 3
    timeout: Optional[float] = None
    enabled: bool = True


class EventBus(LoggerMixin):
    """Central event bus for event-driven architecture."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.kafka_manager = get_kafka_manager()
        
        # Event handlers registry
        self.handlers: Dict[EventType, List[EventHandler]] = defaultdict(list)
        
        # Event queues
        self.event_queues = {
            EventPriority.CRITICAL: asyncio.Queue(),
            EventPriority.HIGH: asyncio.Queue(),
            EventPriority.NORMAL: asyncio.Queue(),
            EventPriority.LOW: asyncio.Queue()
        }
        
        # Processing state
        self.processing = False
        self.processor_tasks = []
        
        # Event statistics
        self.event_stats = {
            'total_events': 0,
            'processed_events': 0,
            'failed_events': 0,
            'events_by_type': defaultdict(int),
            'events_by_status': defaultdict(int)
        }
        
        # Dead letter queue for failed events
        self.dead_letter_queue = asyncio.Queue()
    
    def register_handler(self, event_type: EventType, handler_func: Callable, 
                        handler_id: str = None, async_handler: bool = False,
                        retry_on_failure: bool = True, max_retries: int = 3,
                        timeout: Optional[float] = None) -> str:
        """Register an event handler."""
        try:
            if handler_id is None:
                handler_id = str(uuid.uuid4())
            
            handler = EventHandler(
                handler_id=handler_id,
                event_type=event_type,
                handler_func=handler_func,
                async_handler=async_handler,
                retry_on_failure=retry_on_failure,
                max_retries=max_retries,
                timeout=timeout
            )
            
            self.handlers[event_type].append(handler)
            
            self.logger.info(f"Registered handler {handler_id} for event type {event_type.value}")
            
            return handler_id
            
        except Exception as e:
            self.logger.error(f"Error registering handler: {e}")
            raise
    
    def unregister_handler(self, handler_id: str) -> bool:
        """Unregister an event handler."""
        try:
            for event_type, handlers in self.handlers.items():
                self.handlers[event_type] = [
                    h for h in handlers if h.handler_id != handler_id
                ]
            
            self.logger.info(f"Unregistered handler {handler_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error unregistering handler: {e}")
            return False
    
    async def publish_event(self, event_type: EventType, payload: Dict[str, Any], 
                          source: str = "unknown", priority: EventPriority = EventPriority.NORMAL,
                          correlation_id: str = None, causation_id: str = None) -> str:
        """Publish an event to the event bus."""
        try:
            event = Event(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                priority=priority,
                payload=payload,
                timestamp=datetime.utcnow(),
                source=source,
                correlation_id=correlation_id,
                causation_id=causation_id
            )
            
            # Add to appropriate queue based on priority
            await self.event_queues[priority].put(event)
            
            # Update statistics
            self.event_stats['total_events'] += 1
            self.event_stats['events_by_type'][event_type.value] += 1
            self.event_stats['events_by_status'][EventStatus.PENDING.value] += 1
            
            # Publish to Kafka if available
            if self.kafka_manager:
                stream_message = StreamMessage(
                    timestamp=event.timestamp,
                    message_type="event",
                    data=event.to_dict(),
                    source="event_bus"
                )
                await self.kafka_manager.publish_message("events", stream_message)
            
            self.logger.debug(f"Published event {event.event_id} of type {event_type.value}")
            
            # Record metrics
            self.metrics.record_trading_signal(
                signal_type="event_published",
                asset_symbol=event_type.value
            )
            
            return event.event_id
            
        except Exception as e:
            self.logger.error(f"Error publishing event: {e}")
            raise
    
    async def start_processing(self, num_workers: int = 4):
        """Start event processing workers."""
        try:
            if self.processing:
                return
            
            self.processing = True
            
            # Start worker tasks
            for i in range(num_workers):
                task = asyncio.create_task(self._event_worker(f"worker_{i}"))
                self.processor_tasks.append(task)
            
            # Start dead letter queue processor
            dead_letter_task = asyncio.create_task(self._dead_letter_processor())
            self.processor_tasks.append(dead_letter_task)
            
            self.logger.info(f"Started {num_workers} event processing workers")
            
        except Exception as e:
            self.logger.error(f"Error starting event processing: {e}")
            raise
    
    async def stop_processing(self):
        """Stop event processing workers."""
        try:
            self.processing = False
            
            # Cancel all tasks
            for task in self.processor_tasks:
                task.cancel()
            
            # Wait for tasks to complete
            await asyncio.gather(*self.processor_tasks, return_exceptions=True)
            
            self.processor_tasks.clear()
            
            self.logger.info("Stopped event processing workers")
            
        except Exception as e:
            self.logger.error(f"Error stopping event processing: {e}")
    
    async def _event_worker(self, worker_name: str):
        """Event processing worker."""
        try:
            while self.processing:
                # Get next event (check queues by priority)
                event = await self._get_next_event()
                
                if event is None:
                    await asyncio.sleep(0.1)
                    continue
                
                # Process event
                await self._process_event(event, worker_name)
                
        except asyncio.CancelledError:
            self.logger.info(f"Event worker {worker_name} cancelled")
        except Exception as e:
            self.logger.error(f"Error in event worker {worker_name}: {e}")
    
    async def _get_next_event(self) -> Optional[Event]:
        """Get next event from queues (by priority)."""
        try:
            # Check queues in priority order
            for priority in [EventPriority.CRITICAL, EventPriority.HIGH, 
                            EventPriority.NORMAL, EventPriority.LOW]:
                queue = self.event_queues[priority]
                
                try:
                    event = queue.get_nowait()
                    return event
                except asyncio.QueueEmpty:
                    continue
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting next event: {e}")
            return None
    
    async def _process_event(self, event: Event, worker_name: str):
        """Process a single event."""
        try:
            # Update status
            event.status = EventStatus.PROCESSING
            start_time = datetime.utcnow()
            
            self.logger.debug(f"Worker {worker_name} processing event {event.event_id}")
            
            # Get handlers for this event type
            handlers = self.handlers.get(event.event_type, [])
            
            if not handlers:
                self.logger.warning(f"No handlers registered for event type {event.event_type.value}")
                event.status = EventStatus.COMPLETED
                return
            
            # Process with all handlers
            handler_results = []
            
            for handler in handlers:
                if not handler.enabled:
                    continue
                
                try:
                    result = await self._execute_handler(handler, event)
                    handler_results.append({
                        'handler_id': handler.handler_id,
                        'success': True,
                        'result': result
                    })
                    
                except Exception as e:
                    self.logger.error(f"Handler {handler.handler_id} failed: {e}")
                    
                    handler_results.append({
                        'handler_id': handler.handler_id,
                        'success': False,
                        'error': str(e)
                    })
                    
                    # Check if we should retry
                    if handler.retry_on_failure and event.retry_count < handler.max_retries:
                        event.retry_count += 1
                        event.status = EventStatus.RETRY
                        await self.event_queues[event.priority].put(event)
                        return
            
            # Update event status
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            event.processing_time = processing_time
            
            # Check if any handler failed
            failed_handlers = [r for r in handler_results if not r['success']]
            
            if failed_handlers:
                event.status = EventStatus.FAILED
                event.error_message = f"Failed handlers: {[h['handler_id'] for h in failed_handlers]}"
                
                # Add to dead letter queue if max retries exceeded
                if event.retry_count >= event.max_retries:
                    await self.dead_letter_queue.put(event)
            else:
                event.status = EventStatus.COMPLETED
            
            # Update statistics
            self.event_stats['processed_events'] += 1
            self.event_stats['events_by_status'][event.status.value] += 1
            
            self.logger.debug(f"Worker {worker_name} completed event {event.event_id}")
            
        except Exception as e:
            self.logger.error(f"Error processing event {event.event_id}: {e}")
            event.status = EventStatus.FAILED
            event.error_message = str(e)
            await self.dead_letter_queue.put(event)
    
    async def _execute_handler(self, handler: EventHandler, event: Event) -> Any:
        """Execute a single event handler."""
        try:
            if handler.async_handler:
                # Async handler
                if handler.timeout:
                    result = await asyncio.wait_for(
                        handler.handler_func(event), 
                        timeout=handler.timeout
                    )
                else:
                    result = await handler.handler_func(event)
            else:
                # Sync handler - run in thread pool
                loop = asyncio.get_event_loop()
                
                with ThreadPoolExecutor() as executor:
                    if handler.timeout:
                        result = await asyncio.wait_for(
                            loop.run_in_executor(executor, handler.handler_func, event),
                            timeout=handler.timeout
                        )
                    else:
                        result = await loop.run_in_executor(executor, handler.handler_func, event)
            
            return result
            
        except asyncio.TimeoutError:
            raise Exception(f"Handler {handler.handler_id} timed out after {handler.timeout} seconds")
        except Exception as e:
            raise Exception(f"Handler {handler.handler_id} failed: {e}")
    
    async def _dead_letter_processor(self):
        """Process events from dead letter queue."""
        try:
            while self.processing:
                try:
                    event = await asyncio.wait_for(
                        self.dead_letter_queue.get(), 
                        timeout=1.0
                    )
                    
                    self.logger.error(f"Event {event.event_id} moved to dead letter queue: {event.error_message}")
                    
                    # Update statistics
                    self.event_stats['failed_events'] += 1
                    
                except asyncio.TimeoutError:
                    continue
                    
        except asyncio.CancelledError:
            self.logger.info("Dead letter processor cancelled")
        except Exception as e:
            self.logger.error(f"Error in dead letter processor: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        try:
            return {
                'processing': self.processing,
                'active_workers': len(self.processor_tasks),
                'queue_sizes': {
                    priority.value: queue.qsize()
                    for priority, queue in self.event_queues.items()
                },
                'dead_letter_queue_size': self.dead_letter_queue.qsize(),
                'registered_handlers': {
                    event_type.value: len(handlers)
                    for event_type, handlers in self.handlers.items()
                },
                'event_statistics': dict(self.event_stats),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {}


class EventStore(LoggerMixin):
    """Event store for event sourcing and auditing."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.event_store = {}  # In-memory store (in production, use database)
    
    async def store_event(self, event: Event):
        """Store an event in the event store."""
        try:
            # Store event
            self.event_store[event.event_id] = event.to_dict()
            
            # Cache recent events
            cache_key = f"event:{event.event_id}"
            self.cache.set(cache_key, event.to_dict(), ttl=86400)  # 24 hours TTL
            
            self.logger.debug(f"Stored event {event.event_id} in event store")
            
        except Exception as e:
            self.logger.error(f"Error storing event: {e}")
            raise
    
    async def get_event(self, event_id: str) -> Optional[Event]:
        """Get an event from the event store."""
        try:
            # Check cache first
            cache_key = f"event:{event_id}"
            cached_event = self.cache.get(cache_key)
            
            if cached_event:
                return Event.from_dict(cached_event)
            
            # Check store
            if event_id in self.event_store:
                return Event.from_dict(self.event_store[event_id])
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting event: {e}")
            return None
    
    async def get_events_by_type(self, event_type: EventType, limit: int = 100) -> List[Event]:
        """Get events by type."""
        try:
            events = []
            
            for event_data in self.event_store.values():
                if event_data['event_type'] == event_type.value:
                    events.append(Event.from_dict(event_data))
            
            # Sort by timestamp (newest first) and limit
            events.sort(key=lambda e: e.timestamp, reverse=True)
            
            return events[:limit]
            
        except Exception as e:
            self.logger.error(f"Error getting events by type: {e}")
            return []
    
    async def get_events_by_correlation(self, correlation_id: str) -> List[Event]:
        """Get events by correlation ID."""
        try:
            events = []
            
            for event_data in self.event_store.values():
                if event_data.get('correlation_id') == correlation_id:
                    events.append(Event.from_dict(event_data))
            
            # Sort by timestamp
            events.sort(key=lambda e: e.timestamp)
            
            return events
            
        except Exception as e:
            self.logger.error(f"Error getting events by correlation: {e}")
            return []


class EventSourcing(LoggerMixin):
    """Event sourcing for aggregate state reconstruction."""
    
    def __init__(self, event_store: EventStore):
        self.event_store = event_store
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.aggregates = {}  # aggregate_id -> list of events
    
    async def apply_event(self, aggregate_id: str, event: Event):
        """Apply an event to an aggregate."""
        try:
            # Store event
            await self.event_store.store_event(event)
            
            # Add to aggregate
            if aggregate_id not in self.aggregates:
                self.aggregates[aggregate_id] = []
            
            self.aggregates[aggregate_id].append(event)
            
            # Cache aggregate state
            cache_key = f"aggregate:{aggregate_id}"
            self.cache.set(cache_key, len(self.aggregates[aggregate_id]), ttl=3600)
            
            self.logger.debug(f"Applied event {event.event_id} to aggregate {aggregate_id}")
            
        except Exception as e:
            self.logger.error(f"Error applying event: {e}")
            raise
    
    async def get_aggregate_events(self, aggregate_id: str, from_version: int = 0) -> List[Event]:
        """Get events for an aggregate from a specific version."""
        try:
            if aggregate_id not in self.aggregates:
                return []
            
            events = self.aggregates[aggregate_id]
            
            # Filter from version
            if from_version > 0:
                events = events[from_version:]
            
            return events
            
        except Exception as e:
            self.logger.error(f"Error getting aggregate events: {e}")
            return []
    
    async def replay_events(self, aggregate_id: str, event_handlers: Dict[EventType, Callable]) -> Any:
        """Replay events to reconstruct aggregate state."""
        try:
            events = await self.get_aggregate_events(aggregate_id)
            
            # Reconstruct state
            state = None
            
            for event in events:
                handler = event_handlers.get(event.event_type)
                if handler:
                    state = handler(state, event)
            
            return state
            
        except Exception as e:
            self.logger.error(f"Error replaying events: {e}")
            raise


# Global instances
event_bus = EventBus()
event_store = EventStore()
event_sourcing = EventSourcing(event_store)


def get_event_bus() -> EventBus:
    """Get event bus instance."""
    return event_bus


def get_event_store() -> EventStore:
    """Get event store instance."""
    return event_store


def get_event_sourcing() -> EventSourcing:
    """Get event sourcing instance."""
    return event_sourcing


# Utility functions
async def publish_market_data_event(asset_symbol: str, price_data: Dict[str, Any]):
    """Publish market data event."""
    await event_bus.publish_event(
        EventType.MARKET_DATA_RECEIVED,
        {
            'asset_symbol': asset_symbol,
            'price_data': price_data,
            'timestamp': datetime.utcnow().isoformat()
        },
        source="market_data_service",
        priority=EventPriority.HIGH
    )


async def publish_prediction_event(asset_symbol: str, prediction: Dict[str, Any]):
    """Publish prediction event."""
    await event_bus.publish_event(
        EventType.PREDICTION_GENERATED,
        {
            'asset_symbol': asset_symbol,
            'prediction': prediction,
            'timestamp': datetime.utcnow().isoformat()
        },
        source="prediction_service",
        priority=EventPriority.NORMAL
    )


async def publish_trade_event(trade_data: Dict[str, Any]):
    """Publish trade execution event."""
    await event_bus.publish_event(
        EventType.TRADE_EXECUTED,
        {
            'trade_data': trade_data,
            'timestamp': datetime.utcnow().isoformat()
        },
        source="trading_service",
        priority=EventPriority.CRITICAL
    )


async def publish_risk_alert(risk_data: Dict[str, Any]):
    """Publish risk alert event."""
    await event_bus.publish_event(
        EventType.RISK_ALERT,
        {
            'risk_data': risk_data,
            'timestamp': datetime.utcnow().isoformat()
        },
        source="risk_service",
        priority=EventPriority.HIGH
    )


# Decorators for event handling
def event_handler(event_type: EventType, handler_id: str = None, async_handler: bool = False):
    """Decorator for event handlers."""
    def decorator(func):
        # Generate handler ID if not provided
        if handler_id is None:
            actual_handler_id = f"{func.__module__}.{func.__name__}"
        else:
            actual_handler_id = handler_id
        
        # Register handler
        event_bus.register_handler(
            event_type=event_type,
            handler_func=func,
            handler_id=actual_handler_id,
            async_handler=async_handler
        )
        
        return func
    return decorator


# Event-driven command pattern
class CommandHandler(LoggerMixin):
    """Base class for command handlers."""
    
    def __init__(self):
        self.event_bus = get_event_bus()
        self.event_store = get_event_store()
    
    async def handle(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a command and publish events."""
        raise NotImplementedError


# Example usage
class TradingCommandHandler(CommandHandler):
    """Example command handler for trading operations."""
    
    @event_handler(EventType.TRADE_EXECUTED, async_handler=True)
    async def handle_trade_executed(self, event: Event):
        """Handle trade executed event."""
        trade_data = event.payload.get('trade_data', {})
        
        # Update portfolio state
        # Send notifications
        # Update analytics
        
        self.logger.info(f"Handled trade executed event: {trade_data}")
    
    async def execute_trade(self, trade_data: Dict[str, Any]) -> str:
        """Execute a trade command."""
        try:
            # Execute trade logic
            # ...
            
            # Publish event
            await self.event_bus.publish_event(
                EventType.TRADE_EXECUTED,
                {'trade_data': trade_data},
                source="trading_command_handler",
                priority=EventPriority.CRITICAL
            )
            
            return "trade_executed"
            
        except Exception as e:
            self.logger.error(f"Error executing trade: {e}")
            raise
