"""
WebSocket API endpoints for real-time updates.
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
import asyncio

from app.infrastructure.streaming import get_websocket_manager, MarketDataMessage, PredictionMessage
from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.metrics import get_metrics

logger = logging.getLogger(__name__)

# Initialize SocketIO
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')


class WebSocketHandler(LoggerMixin):
    """WebSocket event handlers for real-time updates."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.websocket_manager = get_websocket_manager()
        self.connected_clients = {}  # client_id -> client_info
    
    def register_client_handlers(self):
        """Register all WebSocket event handlers."""
        
        @socketio.on('connect')
        def handle_connect():
            client_id = request.sid
            client_info = {
                "client_id": client_id,
                "connected_at": datetime.utcnow(),
                "subscriptions": set(),
                "user_agent": request.headers.get('User-Agent', 'unknown')
            }
            
            self.connected_clients[client_id] = client_info
            
            # Register with WebSocket manager
            asyncio.run_coroutine_threadsafe(
                self.websocket_manager.register_client(None, client_id),
                asyncio.new_event_loop()
            )
            
            self.logger.info(f"Client {client_id} connected")
            
            # Send initial connection message
            emit('connected', {
                "client_id": client_id,
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Connected to Sentinel Trading WebSocket"
            })
            
            # Update metrics
            self.metrics.record_trading_signal(
                signal_type="websocket_client_connected",
                asset_symbol=client_id
            )
        
        @socketio.on('disconnect')
        def handle_disconnect():
            client_id = request.sid
            
            # Unregister from WebSocket manager
            asyncio.run_coroutine_threadsafe(
                self.websocket_manager.unregister_client(None, client_id),
                asyncio.new_event_loop()
            )
            
            # Remove from connected clients
            if client_id in self.connected_clients:
                del self.connected_clients[client_id]
            
            self.logger.info(f"Client {client_id} disconnected")
            
            # Update metrics
            self.metrics.record_trading_signal(
                signal_type="websocket_client_disconnected",
                asset_symbol=client_id
            )
        
        @socketio.on('subscribe')
        def handle_subscribe(data):
            """Handle subscription requests."""
            client_id = request.sid
            topic = data.get('topic')
            
            if not topic:
                emit('error', {
                    "error": "Topic is required",
                    "timestamp": datetime.utcnow().isoformat()
                })
                return
            
            # Validate topic
            valid_topics = ['market_data', 'predictions', 'alerts', 'all']
            if topic not in valid_topics:
                emit('error', {
                    "error": f"Invalid topic. Valid topics: {valid_topics}",
                    "timestamp": datetime.utcnow().isoformat()
                })
                return
            
            # Add subscription
            if client_id in self.connected_clients:
                self.connected_clients[client_id]["subscriptions"].add(topic)
            
            # Join SocketIO room for topic
            join_room(topic)
            
            # Register with WebSocket manager
            asyncio.run_coroutine_threadsafe(
                self.websocket_manager.subscribe(None, topic),
                asyncio.new_event_loop()
            )
            
            self.logger.info(f"Client {client_id} subscribed to {topic}")
            
            emit('subscribed', {
                "topic": topic,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        @socketio.on('unsubscribe')
        def handle_unsubscribe(data):
            """Handle unsubscription requests."""
            client_id = request.sid
            topic = data.get('topic')
            
            if not topic:
                emit('error', {
                    "error": "Topic is required",
                    "timestamp": datetime.utcnow().isoformat()
                })
                return
            
            # Remove subscription
            if client_id in self.connected_clients:
                self.connected_clients[client_id]["subscriptions"].discard(topic)
            
            # Leave SocketIO room
            leave_room(topic)
            
            # Unregister from WebSocket manager
            asyncio.run_coroutine_threadsafe(
                self.websocket_manager.unsubscribe(None, topic),
                asyncio.new_event_loop()
            )
            
            self.logger.info(f"Client {client_id} unsubscribed from {topic}")
            
            emit('unsubscribed', {
                "topic": topic,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        @socketio.on('get_subscriptions')
        def handle_get_subscriptions():
            """Get current subscriptions."""
            client_id = request.sid
            
            if client_id in self.connected_clients:
                subscriptions = list(self.connected_clients[client_id]["subscriptions"])
            else:
                subscriptions = []
            
            emit('subscriptions', {
                "subscriptions": subscriptions,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        @socketio.on('get_client_info')
        def handle_get_client_info():
            """Get client information."""
            client_id = request.sid
            
            if client_id in self.connected_clients:
                client_info = self.connected_clients[client_id].copy()
                client_info["subscriptions"] = list(client_info["subscriptions"])
            else:
                client_info = {"error": "Client not found"}
            
            emit('client_info', {
                "client_info": client_info,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        @socketio.on('ping')
        def handle_ping():
            """Handle ping for connection health check."""
            emit('pong', {
                "timestamp": datetime.utcnow().isoformat()
            })
    
    def broadcast_market_data(self, asset_symbol: str, price: float, volume: float, **kwargs):
        """Broadcast market data to subscribed clients."""
        message = MarketDataMessage(
            timestamp=datetime.utcnow(),
            asset_symbol=asset_symbol,
            price=price,
            volume=volume,
            source="sentinel_trading",
            data={"asset_symbol": asset_symbol, "price": price, "volume": volume},
            **kwargs
        )
        
        # Broadcast to WebSocket manager
        asyncio.run_coroutine_threadsafe(
            self.websocket_manager.send_market_data(message),
            asyncio.new_event_loop()
        )
        
        # Also emit via SocketIO to room
        socketio.emit('market_data', message.to_dict(), room='market_data')
        
        self.logger.debug(f"Broadcast market data for {asset_symbol}: ${price}")
    
    def broadcast_prediction(self, asset_symbol: str, prediction: str, confidence: float, **kwargs):
        """Broadcast prediction to subscribed clients."""
        message = PredictionMessage(
            timestamp=datetime.utcnow(),
            asset_symbol=asset_symbol,
            prediction=prediction,
            confidence=confidence,
            source="sentinel_trading",
            data={"asset_symbol": asset_symbol, "prediction": prediction, "confidence": confidence},
            **kwargs
        )
        
        # Broadcast to WebSocket manager
        asyncio.run_coroutine_threadsafe(
            self.websocket_manager.send_prediction(message),
            asyncio.new_event_loop()
        )
        
        # Also emit via SocketIO to room
        socketio.emit('prediction', message.to_dict(), room='predictions')
        
        self.logger.debug(f"Broadcast prediction for {asset_symbol}: {prediction} ({confidence:.2f})")
    
    def broadcast_alert(self, alert_type: str, alert_data: Dict[str, Any]):
        """Broadcast alert to all clients."""
        alert_message = {
            "type": "alert",
            "alert_type": alert_type,
            "data": alert_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Broadcast to WebSocket manager
        asyncio.run_coroutine_threadsafe(
            self.websocket_manager.send_alert(alert_type, alert_data),
            asyncio.new_event_loop()
        )
        
        # Also emit via SocketIO to room
        socketio.emit('alert', alert_message, room='alerts')
        
        self.logger.info(f"Broadcast alert: {alert_type}")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics."""
        return {
            "connected_clients": len(self.connected_clients),
            "total_subscriptions": sum(
                len(client_info["subscriptions"]) 
                for client_info in self.connected_clients.values()
            ),
            "subscriptions_by_topic": self._get_subscriptions_by_topic(),
            "clients": [
                {
                    "client_id": client_id,
                    "connected_at": client_info["connected_at"].isoformat(),
                    "subscriptions": list(client_info["subscriptions"]),
                    "user_agent": client_info["user_agent"]
                }
                for client_id, client_info in self.connected_clients.items()
            ]
        }
    
    def _get_subscriptions_by_topic(self) -> Dict[str, int]:
        """Get subscription count by topic."""
        topic_counts = {}
        
        for client_info in self.connected_clients.values():
            for topic in client_info["subscriptions"]:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
        
        return topic_counts


# Global WebSocket handler
websocket_handler = WebSocketHandler()


def init_websocket():
    """Initialize WebSocket handlers."""
    websocket_handler.register_client_handlers()
    logger.info("WebSocket handlers initialized")


def get_websocket_handler() -> WebSocketHandler:
    """Get WebSocket handler instance."""
    return websocket_handler


# API endpoints for WebSocket management
def register_websocket_api(app):
    """Register WebSocket API endpoints."""
    
    @app.route('/api/websocket/stats')
    def websocket_stats():
        """Get WebSocket connection statistics."""
        return jsonify(websocket_handler.get_connection_stats())
    
    @app.route('/api/websocket/broadcast/market_data', methods=['POST'])
    def broadcast_market_data():
        """Broadcast market data to all subscribers."""
        data = request.get_json()
        
        asset_symbol = data.get('asset_symbol')
        price = data.get('price')
        volume = data.get('volume')
        
        if not all([asset_symbol, price, volume]):
            return jsonify({
                "error": "asset_symbol, price, and volume are required"
            }), 400
        
        try:
            websocket_handler.broadcast_market_data(
                asset_symbol=asset_symbol,
                price=float(price),
                volume=float(volume),
                high=data.get('high'),
                low=data.get('low'),
                open_price=data.get('open'),
                change=data.get('change'),
                change_percent=data.get('change_percent')
            )
            
            return jsonify({
                "message": "Market data broadcasted successfully",
                "timestamp": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error broadcasting market data: {e}")
            return jsonify({
                "error": str(e)
            }), 500
    
    @app.route('/api/websocket/broadcast/prediction', methods=['POST'])
    def broadcast_prediction():
        """Broadcast prediction to all subscribers."""
        data = request.get_json()
        
        asset_symbol = data.get('asset_symbol')
        prediction = data.get('prediction')
        confidence = data.get('confidence')
        
        if not all([asset_symbol, prediction, confidence is not None]):
            return jsonify({
                "error": "asset_symbol, prediction, and confidence are required"
            }), 400
        
        try:
            websocket_handler.broadcast_prediction(
                asset_symbol=asset_symbol,
                prediction=prediction,
                confidence=float(confidence),
                target_price=data.get('target_price'),
                time_horizon=data.get('time_horizon'),
                model_version=data.get('model_version')
            )
            
            return jsonify({
                "message": "Prediction broadcasted successfully",
                "timestamp": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error broadcasting prediction: {e}")
            return jsonify({
                "error": str(e)
            }), 500
    
    @app.route('/api/websocket/broadcast/alert', methods=['POST'])
    def broadcast_alert():
        """Broadcast alert to all clients."""
        data = request.get_json()
        
        alert_type = data.get('alert_type')
        alert_data = data.get('data')
        
        if not all([alert_type, alert_data]):
            return jsonify({
                "error": "alert_type and data are required"
            }), 400
        
        try:
            websocket_handler.broadcast_alert(alert_type, alert_data)
            
            return jsonify({
                "message": "Alert broadcasted successfully",
                "timestamp": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error broadcasting alert: {e}")
            return jsonify({
                "error": str(e)
            }), 500


# Utility functions for broadcasting
def broadcast_market_data_update(asset_symbol: str, price: float, volume: float, **kwargs):
    """Broadcast market data update."""
    websocket_handler.broadcast_market_data(asset_symbol, price, volume, **kwargs)


def broadcast_prediction_update(asset_symbol: str, prediction: str, confidence: float, **kwargs):
    """Broadcast prediction update."""
    websocket_handler.broadcast_prediction(asset_symbol, prediction, confidence, **kwargs)


def broadcast_price_alert(asset_symbol: str, price: float, change_percent: float):
    """Broadcast price alert."""
    alert_data = {
        "asset_symbol": asset_symbol,
        "current_price": price,
        "change_percent": change_percent,
        "alert_message": f"Significant price movement for {asset_symbol}: {change_percent:.2f}%"
    }
    
    websocket_handler.broadcast_alert("price_alert", alert_data)


def broadcast_prediction_alert(asset_symbol: str, prediction: str, confidence: float, target_price: float = None):
    """Broadcast high confidence prediction alert."""
    alert_data = {
        "asset_symbol": asset_symbol,
        "prediction": prediction,
        "confidence": confidence,
        "target_price": target_price,
        "alert_message": f"High confidence prediction for {asset_symbol}: {prediction} ({confidence:.2f})"
    }
    
    websocket_handler.broadcast_alert("prediction_alert", alert_data)


def broadcast_system_alert(message: str, severity: str = "info"):
    """Broadcast system alert."""
    alert_data = {
        "message": message,
        "severity": severity,
        "alert_message": message
    }
    
    websocket_handler.broadcast_alert("system_alert", alert_data)
