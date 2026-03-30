"""
Live prediction updates and real-time prediction API endpoints.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import Blueprint, jsonify, request
import pandas as pd

from app.infrastructure.streaming import get_kafka_manager, publish_prediction, PredictionMessage
from app.infrastructure.cache import get_cache
from app.infrastructure.metrics import get_metrics
from app.infrastructure.logging_config import LoggerMixin
from app.container import get_container
from app.api.websocket import broadcast_prediction_update, broadcast_prediction_alert

logger = logging.getLogger(__name__)

live_predictions_bp = Blueprint('live_predictions', __name__, url_prefix='/live-predictions')


class LivePredictionUpdater(LoggerMixin):
    """Live prediction update service."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.kafka_manager = get_kafka_manager()
        self.update_interval = 300  # 5 minutes
        self.last_updates = {}  # asset_id -> last_update_time
        self.prediction_alerts_sent = {}  # asset_id -> last_alert_sent
        self.confidence_threshold = 0.8  # High confidence threshold
    
    async def start_prediction_updates(self, asset_ids: List[int] = None):
        """Start live prediction updates for specified assets."""
        try:
            container = get_container()
            asset_repo = container.asset_repository()
            
            # Get assets to update
            if asset_ids is None:
                assets = asset_repo.get_all()
                asset_ids = [asset.id for asset in assets]
            
            self.logger.info(f"Starting live prediction updates for {len(asset_ids)} assets")
            
            # Start update loop
            asyncio.create_task(self._prediction_update_loop(asset_ids))
            
        except Exception as e:
            self.logger.error(f"Error starting prediction updates: {e}")
            raise
    
    async def _prediction_update_loop(self, asset_ids: List[int]):
        """Main prediction update loop."""
        while True:
            try:
                start_time = datetime.utcnow()
                
                # Update predictions for all assets
                for asset_id in asset_ids:
                    await self._update_asset_prediction(asset_id)
                
                # Log performance
                duration = (datetime.utcnow() - start_time).total_seconds()
                self.logger.debug(f"Prediction update cycle completed in {duration:.2f}s for {len(asset_ids)} assets")
                
                # Update metrics
                self.metrics.record_trading_signal(
                    signal_type="prediction_update_cycle",
                    asset_symbol=f"assets_{len(asset_ids)}"
                )
                
                # Wait for next update
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                self.logger.error(f"Error in prediction update loop: {e}")
                await asyncio.sleep(30)  # Wait before retrying
    
    async def _update_asset_prediction(self, asset_id: int):
        """Update prediction for a single asset."""
        try:
            container = get_container()
            asset_repo = container.asset_repository()
            
            # Get asset information
            asset = asset_repo.get_by_id(asset_id)
            if not asset:
                return
            
            # Generate new prediction
            prediction_data = await self._generate_prediction(asset)
            
            if prediction_data:
                # Store in cache
                cache_key = f"live_prediction:{asset.symbol}"
                self.cache.set(cache_key, prediction_data, ttl=600)  # 10 minutes TTL
                
                # Publish to Kafka
                await publish_prediction(
                    asset_symbol=asset.symbol,
                    prediction=prediction_data['prediction'],
                    confidence=prediction_data['confidence'],
                    target_price=prediction_data.get('target_price'),
                    time_horizon=prediction_data.get('time_horizon'),
                    model_version=prediction_data.get('model_version')
                )
                
                # Broadcast via WebSocket
                broadcast_prediction_update(
                    asset_symbol=asset.symbol,
                    prediction=prediction_data['prediction'],
                    confidence=prediction_data['confidence'],
                    target_price=prediction_data.get('target_price'),
                    time_horizon=prediction_data.get('time_horizon'),
                    model_version=prediction_data.get('model_version')
                )
                
                # Check for high confidence alerts
                await self._check_prediction_alerts(asset.symbol, prediction_data)
                
                # Update last update time
                self.last_updates[asset_id] = datetime.utcnow()
                
                self.logger.debug(f"Updated prediction for {asset.symbol}: {prediction_data['prediction']} ({prediction_data['confidence']:.2f})")
        
        except Exception as e:
            self.logger.error(f"Error updating prediction for asset {asset_id}: {e}")
    
    async def _generate_prediction(self, asset) -> Dict[str, Any]:
        """Generate new prediction for asset."""
        try:
            container = get_container()
            
            # Use existing prediction use case
            use_case = container.run_predictions_use_case()
            
            # Generate prediction for single asset
            # This would require modifying the use case to handle single assets
            # For now, we'll create a mock prediction
            import random
            
            predictions = ['BUY', 'SELL', 'HOLD']
            prediction = random.choice(predictions)
            confidence = random.uniform(0.6, 0.95)
            
            # Get current price for target price calculation
            price_cache_key = f"realtime_price:{asset.symbol}"
            current_price_data = self.cache.get(price_cache_key)
            
            target_price = None
            if current_price_data:
                current_price = current_price_data['price']
                
                # Calculate target price based on prediction
                if prediction == 'BUY':
                    target_price = current_price * (1 + random.uniform(0.02, 0.10))  # 2-10% upside
                elif prediction == 'SELL':
                    target_price = current_price * (1 - random.uniform(0.02, 0.10))  # 2-10% downside
                else:
                    target_price = current_price  # HOLD - same price
            
            return {
                'prediction': prediction,
                'confidence': confidence,
                'target_price': target_price,
                'time_horizon': random.choice([7, 14, 30]),  # days
                'model_version': '1.0.0',
                'timestamp': datetime.utcnow().isoformat(),
                'source': 'sentinel_trading'
            }
        
        except Exception as e:
            self.logger.error(f"Error generating prediction for {asset.symbol}: {e}")
            return None
    
    async def _check_prediction_alerts(self, asset_symbol: str, prediction_data: Dict[str, Any]):
        """Check for high confidence prediction alerts."""
        try:
            confidence = prediction_data.get('confidence', 0)
            prediction = prediction_data.get('prediction', '')
            
            # Alert on high confidence predictions
            if confidence >= self.confidence_threshold:
                # Check if we haven't sent an alert recently (avoid spam)
                last_alert_time = self.prediction_alerts_sent.get(asset_symbol)
                if last_alert_time is None or (datetime.utcnow() - last_alert_time) > timedelta(minutes=30):
                    
                    broadcast_prediction_alert(
                        asset_symbol=asset_symbol,
                        prediction=prediction,
                        confidence=confidence,
                        target_price=prediction_data.get('target_price')
                    )
                    
                    self.prediction_alerts_sent[asset_symbol] = datetime.utcnow()
                    
                    self.logger.info(f"High confidence prediction alert for {asset_symbol}: {prediction} ({confidence:.2f})")
        
        except Exception as e:
            self.logger.error(f"Error checking prediction alerts for {asset_symbol}: {e}")
    
    def get_prediction(self, asset_symbol: str) -> Optional[Dict[str, Any]]:
        """Get current prediction from cache."""
        try:
            cache_key = f"live_prediction:{asset_symbol}"
            return self.cache.get(cache_key)
        except Exception as e:
            self.logger.error(f"Error getting prediction from cache: {e}")
            return None
    
    def get_all_predictions(self) -> Dict[str, Any]:
        """Get all current predictions from cache."""
        try:
            predictions = {}
            
            # Get all prediction cache keys
            cache_keys = self.cache.keys("live_prediction:*")
            
            for key in cache_keys:
                asset_symbol = key.split(":")[-1]
                prediction_data = self.cache.get(key)
                if prediction_data:
                    predictions[asset_symbol] = prediction_data
            
            return predictions
        
        except Exception as e:
            self.logger.error(f"Error getting all predictions from cache: {e}")
            return {}
    
    def get_update_stats(self) -> Dict[str, Any]:
        """Get prediction update statistics."""
        now = datetime.utcnow()
        
        # Calculate update frequencies
        recent_updates = sum(
            1 for last_update in self.last_updates.values()
            if (now - last_update) < timedelta(minutes=10)
        )
        
        return {
            "total_assets_tracked": len(self.last_updates),
            "recent_updates": recent_updates,
            "last_updates": {
                asset_id: last_update.isoformat()
                for asset_id, last_update in self.last_updates.items()
            },
            "prediction_alerts_sent": len(self.prediction_alerts_sent),
            "update_interval_seconds": self.update_interval,
            "confidence_threshold": self.confidence_threshold
        }
    
    def force_update_prediction(self, asset_symbol: str) -> bool:
        """Force update prediction for specific asset."""
        try:
            container = get_container()
            asset_repo = container.asset_repository()
            
            # Get asset
            asset = asset_repo.get_by_symbol(asset_symbol)
            if not asset:
                return False
            
            # Run update in background
            asyncio.run_coroutine_threadsafe(
                self._update_asset_prediction(asset.id),
                asyncio.new_event_loop()
            )
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error forcing prediction update for {asset_symbol}: {e}")
            return False


# Global prediction updater instance
prediction_updater = LivePredictionUpdater()


def get_prediction_updater() -> LivePredictionUpdater:
    """Get prediction updater instance."""
    return prediction_updater


# API endpoints
@live_predictions_bp.route('/predictions')
def get_predictions():
    """Get current predictions for all assets."""
    try:
        predictions = prediction_updater.get_all_predictions()
        
        return jsonify({
            "predictions": predictions,
            "timestamp": datetime.utcnow().isoformat(),
            "count": len(predictions)
        })
        
    except Exception as e:
        logger.error(f"Error getting predictions: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@live_predictions_bp.route('/predictions/<asset_symbol>')
def get_prediction(asset_symbol: str):
    """Get current prediction for specific asset."""
    try:
        prediction_data = prediction_updater.get_prediction(asset_symbol)
        
        if not prediction_data:
            return jsonify({
                "error": f"Prediction data not found for {asset_symbol}",
                "timestamp": datetime.utcnow().isoformat()
            }), 404
        
        return jsonify({
            "asset_symbol": asset_symbol,
            "prediction_data": prediction_data,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting prediction for {asset_symbol}: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@live_predictions_bp.route('/predictions/start', methods=['POST'])
def start_prediction_updates():
    """Start live prediction updates."""
    try:
        data = request.get_json()
        asset_ids = data.get('asset_ids')  # Optional list of asset IDs
        
        # Start prediction updates
        asyncio.run_coroutine_threadsafe(
            prediction_updater.start_prediction_updates(asset_ids),
            asyncio.new_event_loop()
        )
        
        return jsonify({
            "message": "Live prediction updates started",
            "asset_ids": asset_ids or "all",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error starting prediction updates: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@live_predictions_bp.route('/predictions/<asset_symbol>/update', methods=['POST'])
def force_update_prediction(asset_symbol: str):
    """Force update prediction for specific asset."""
    try:
        success = prediction_updater.force_update_prediction(asset_symbol)
        
        if success:
            return jsonify({
                "message": f"Prediction update triggered for {asset_symbol}",
                "timestamp": datetime.utcnow().isoformat()
            })
        else:
            return jsonify({
                "error": f"Failed to update prediction for {asset_symbol}",
                "timestamp": datetime.utcnow().isoformat()
            }), 400
        
    except Exception as e:
        logger.error(f"Error forcing prediction update for {asset_symbol}: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@live_predictions_bp.route('/predictions/stats')
def get_prediction_stats():
    """Get prediction update statistics."""
    try:
        stats = prediction_updater.get_update_stats()
        
        return jsonify({
            "stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting prediction stats: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@live_predictions_bp.route('/predictions/history/<asset_symbol>')
def get_prediction_history(asset_symbol: str):
    """Get recent prediction history for an asset."""
    try:
        # Get parameters
        days = request.args.get('days', 7, type=int)
        limit = request.args.get('limit', 50, type=int)
        
        container = get_container()
        prediction_repo = container.prediction_repository()
        asset_repo = container.asset_repository()
        
        # Get asset
        asset = asset_repo.get_by_symbol(asset_symbol)
        if not asset:
            return jsonify({
                "error": f"Asset {asset_symbol} not found",
                "timestamp": datetime.utcnow().isoformat()
            }), 404
        
        # Get historical predictions
        start_date = datetime.utcnow() - timedelta(days=days)
        predictions = prediction_repo.get_by_asset_and_date_range(asset.id, start_date, datetime.utcnow())
        
        # Convert to list
        history = []
        for prediction in predictions[:limit]:
            history.append({
                "id": prediction.id,
                "target_date": prediction.target_date.isoformat(),
                "signal": prediction.signal,
                "confidence": prediction.confidence,
                "target_price": prediction.target_price,
                "time_horizon": prediction.time_horizon,
                "model_version": prediction.model_version,
                "created_at": prediction.created_at.isoformat()
            })
        
        return jsonify({
            "asset_symbol": asset_symbol,
            "history": history,
            "period_days": days,
            "count": len(history),
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting prediction history for {asset_symbol}: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@live_predictions_bp.route('/predictions/alerts')
def get_prediction_alerts():
    """Get recent prediction alerts."""
    try:
        hours = request.args.get('hours', 1, type=int)
        
        # Get alerts from cache
        cache = get_cache()
        alert_keys = cache.keys("prediction_alert:*")
        
        alerts = []
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        for key in alert_keys:
            alert_data = cache.get(key)
            if alert_data:
                alert_time = datetime.fromisoformat(alert_data['timestamp'])
                if alert_time > cutoff_time:
                    alerts.append(alert_data)
        
        # Sort by timestamp
        alerts.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({
            "alerts": alerts,
            "period_hours": hours,
            "count": len(alerts),
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting prediction alerts: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@live_predictions_bp.route('/predictions/performance')
def get_prediction_performance():
    """Get prediction performance metrics."""
    try:
        days = request.args.get('days', 30, type=int)
        
        container = get_container()
        eval_repo = container.prediction_evaluation_repository()
        
        # Get recent evaluations
        start_date = datetime.utcnow() - timedelta(days=days)
        evaluations = eval_repo.get_evaluations_since(start_date)
        
        if not evaluations:
            return jsonify({
                "performance": {
                    "total_evaluations": 0,
                    "accuracy": 0.0,
                    "signal_accuracy": {},
                    "avg_confidence": 0.0
                },
                "period_days": days,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        # Calculate performance metrics
        total_evaluations = len(evaluations)
        correct_predictions = sum(1 for e in evaluations if e.accuracy)
        overall_accuracy = correct_predictions / total_evaluations
        
        # Signal-specific accuracy
        signal_accuracy = {}
        signal_counts = {}
        signal_correct = {}
        
        for evaluation in evaluations:
            signal = evaluation.actual_signal  # The actual signal we're comparing against
            if signal not in signal_counts:
                signal_counts[signal] = 0
                signal_correct[signal] = 0
            
            signal_counts[signal] += 1
            if evaluation.accuracy:
                signal_correct[signal] += 1
        
        for signal in signal_counts:
            signal_accuracy[signal] = signal_correct[signal] / signal_counts[signal]
        
        # Average confidence
        avg_confidence = sum(e.prediction.confidence for e in evaluations) / total_evaluations
        
        performance = {
            "total_evaluations": total_evaluations,
            "accuracy": overall_accuracy,
            "signal_accuracy": signal_accuracy,
            "avg_confidence": avg_confidence
        }
        
        return jsonify({
            "performance": performance,
            "period_days": days,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting prediction performance: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@live_predictions_bp.route('/health')
def live_predictions_health():
    """Health check for live prediction services."""
    try:
        stats = prediction_updater.get_update_stats()
        
        health = {
            "status": "healthy",
            "prediction_updater": {
                "active": stats["total_assets_tracked"] > 0,
                "assets_tracked": stats["total_assets_tracked"],
                "recent_updates": stats["recent_updates"]
            },
            "websocket": {
                "connected_clients": len(get_websocket_handler().connected_clients)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Determine overall status
        if stats["recent_updates"] == 0:
            health["status"] = "degraded"
        
        return jsonify(health)
        
    except Exception as e:
        logger.error(f"Error in live predictions health check: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500
