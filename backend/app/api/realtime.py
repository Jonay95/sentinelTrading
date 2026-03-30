"""
Real-time API endpoints for live price updates and streaming data.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import Blueprint, jsonify, request
import pandas as pd

from app.infrastructure.streaming import get_kafka_manager, publish_market_data, MarketDataMessage
from app.infrastructure.cache import get_cache
from app.infrastructure.metrics import get_metrics
from app.infrastructure.logging_config import LoggerMixin
from app.container import get_container
from app.api.websocket import broadcast_market_data_update, broadcast_price_alert

logger = logging.getLogger(__name__)

realtime_bp = Blueprint('realtime', __name__, url_prefix='/realtime')


class RealTimePriceUpdater(LoggerMixin):
    """Real-time price update service."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.kafka_manager = get_kafka_manager()
        self.update_interval = 30  # seconds
        self.last_updates = {}  # asset_id -> last_update_time
        self.price_alerts_sent = {}  # asset_id -> last_alert_sent
    
    async def start_price_updates(self, asset_ids: List[int] = None):
        """Start real-time price updates for specified assets."""
        try:
            container = get_container()
            asset_repo = container.asset_repository()
            
            # Get assets to update
            if asset_ids is None:
                assets = asset_repo.get_all()
                asset_ids = [asset.id for asset in assets]
            
            self.logger.info(f"Starting real-time price updates for {len(asset_ids)} assets")
            
            # Start update loop
            asyncio.create_task(self._price_update_loop(asset_ids))
            
        except Exception as e:
            self.logger.error(f"Error starting price updates: {e}")
            raise
    
    async def _price_update_loop(self, asset_ids: List[int]):
        """Main price update loop."""
        while True:
            try:
                start_time = datetime.utcnow()
                
                # Update prices for all assets
                for asset_id in asset_ids:
                    await self._update_asset_price(asset_id)
                
                # Log performance
                duration = (datetime.utcnow() - start_time).total_seconds()
                self.logger.debug(f"Price update cycle completed in {duration:.2f}s for {len(asset_ids)} assets")
                
                # Update metrics
                self.metrics.record_trading_signal(
                    signal_type="price_update_cycle",
                    asset_symbol=f"assets_{len(asset_ids)}"
                )
                
                # Wait for next update
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                self.logger.error(f"Error in price update loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _update_asset_price(self, asset_id: int):
        """Update price for a single asset."""
        try:
            container = get_container()
            asset_repo = container.asset_repository()
            
            # Get asset information
            asset = asset_repo.get_by_id(asset_id)
            if not asset:
                return
            
            # Fetch current price from external API
            current_data = await self._fetch_current_price(asset)
            
            if current_data:
                # Store in cache
                cache_key = f"realtime_price:{asset.symbol}"
                self.cache.set(cache_key, current_data, ttl=60)  # 1 minute TTL
                
                # Publish to Kafka
                await publish_market_data(
                    asset_symbol=asset.symbol,
                    price=current_data['price'],
                    volume=current_data.get('volume', 0),
                    high=current_data.get('high'),
                    low=current_data.get('low'),
                    open_price=current_data.get('open'),
                    change=current_data.get('change'),
                    change_percent=current_data.get('change_percent')
                )
                
                # Broadcast via WebSocket
                broadcast_market_data_update(
                    asset_symbol=asset.symbol,
                    price=current_data['price'],
                    volume=current_data.get('volume', 0),
                    high=current_data.get('high'),
                    low=current_data.get('low'),
                    open_price=current_data.get('open'),
                    change=current_data.get('change'),
                    change_percent=current_data.get('change_percent')
                )
                
                # Check for price alerts
                await self._check_price_alerts(asset.symbol, current_data)
                
                # Update last update time
                self.last_updates[asset_id] = datetime.utcnow()
                
                self.logger.debug(f"Updated price for {asset.symbol}: ${current_data['price']}")
        
        except Exception as e:
            self.logger.error(f"Error updating price for asset {asset_id}: {e}")
    
    async def _fetch_current_price(self, asset) -> Dict[str, Any]:
        """Fetch current price from external API."""
        try:
            # Use existing market data adapters
            if asset.provider == 'coingecko':
                return await self._fetch_coingecko_price(asset)
            elif asset.provider == 'yahoo':
                return await self._fetch_yahoo_price(asset)
            else:
                self.logger.warning(f"Unsupported provider for {asset.symbol}: {asset.provider}")
                return None
        
        except Exception as e:
            self.logger.error(f"Error fetching price for {asset.symbol}: {e}")
            return None
    
    async def _fetch_coingecko_price(self, asset) -> Dict[str, Any]:
        """Fetch price from CoinGecko API."""
        try:
            import requests
            
            # Get CoinGecko ID from external_id
            coin_id = asset.external_id
            if not coin_id:
                return None
            
            url = f"https://api.coingecko.com/api/v3/simple/price"
            params = {
                'ids': coin_id,
                'vs_currencies': 'usd',
                'include_24hr_change': 'true',
                'include_24hr_vol': 'true'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if coin_id in data:
                coin_data = data[coin_id]
                
                return {
                    'price': coin_data['usd'],
                    'change_percent': coin_data.get('usd_24h_change', 0),
                    'volume': coin_data.get('usd_24h_vol', 0),
                    'timestamp': datetime.utcnow().isoformat(),
                    'source': 'coingecko'
                }
            
            return None
        
        except Exception as e:
            self.logger.error(f"Error fetching CoinGecko price: {e}")
            return None
    
    async def _fetch_yahoo_price(self, asset) -> Dict[str, Any]:
        """Fetch price from Yahoo Finance API."""
        try:
            import yfinance as yf
            
            # Get ticker symbol from external_id
            ticker = asset.external_id
            if not ticker:
                return None
            
            # Create ticker object
            stock = yf.Ticker(ticker)
            
            # Get current data
            info = stock.info
            history = stock.history(period="1d")
            
            if not history.empty:
                latest = history.iloc[-1]
                
                return {
                    'price': latest['Close'],
                    'open': latest['Open'],
                    'high': latest['High'],
                    'low': latest['Low'],
                    'volume': latest['Volume'],
                    'change': latest['Close'] - latest['Open'],
                    'change_percent': ((latest['Close'] - latest['Open']) / latest['Open']) * 100,
                    'timestamp': datetime.utcnow().isoformat(),
                    'source': 'yahoo'
                }
            
            return None
        
        except Exception as e:
            self.logger.error(f"Error fetching Yahoo price: {e}")
            return None
    
    async def _check_price_alerts(self, asset_symbol: str, current_data: Dict[str, Any]):
        """Check for price alerts and send notifications."""
        try:
            change_percent = current_data.get('change_percent', 0)
            
            # Alert on significant price movements (>2%)
            if abs(change_percent) > 2.0:
                # Check if we haven't sent an alert recently (avoid spam)
                last_alert_time = self.price_alerts_sent.get(asset_symbol)
                if last_alert_time is None or (datetime.utcnow() - last_alert_time) > timedelta(minutes=15):
                    
                    broadcast_price_alert(
                        asset_symbol=asset_symbol,
                        price=current_data['price'],
                        change_percent=change_percent
                    )
                    
                    self.price_alerts_sent[asset_symbol] = datetime.utcnow()
                    
                    self.logger.info(f"Price alert sent for {asset_symbol}: {change_percent:.2f}%")
        
        except Exception as e:
            self.logger.error(f"Error checking price alerts for {asset_symbol}: {e}")
    
    def get_price(self, asset_symbol: str) -> Optional[Dict[str, Any]]:
        """Get current price from cache."""
        try:
            cache_key = f"realtime_price:{asset_symbol}"
            return self.cache.get(cache_key)
        except Exception as e:
            self.logger.error(f"Error getting price from cache: {e}")
            return None
    
    def get_all_prices(self) -> Dict[str, Any]:
        """Get all current prices from cache."""
        try:
            prices = {}
            
            # Get all price cache keys
            cache_keys = self.cache.keys("realtime_price:*")
            
            for key in cache_keys:
                asset_symbol = key.split(":")[-1]
                price_data = self.cache.get(key)
                if price_data:
                    prices[asset_symbol] = price_data
            
            return prices
        
        except Exception as e:
            self.logger.error(f"Error getting all prices from cache: {e}")
            return {}
    
    def get_update_stats(self) -> Dict[str, Any]:
        """Get price update statistics."""
        now = datetime.utcnow()
        
        # Calculate update frequencies
        recent_updates = sum(
            1 for last_update in self.last_updates.values()
            if (now - last_update) < timedelta(minutes=5)
        )
        
        return {
            "total_assets_tracked": len(self.last_updates),
            "recent_updates": recent_updates,
            "last_updates": {
                asset_id: last_update.isoformat()
                for asset_id, last_update in self.last_updates.items()
            },
            "price_alerts_sent": len(self.price_alerts_sent),
            "update_interval_seconds": self.update_interval
        }


# Global price updater instance
price_updater = RealTimePriceUpdater()


def get_price_updater() -> RealTimePriceUpdater:
    """Get price updater instance."""
    return price_updater


# API endpoints
@realtime_bp.route('/prices')
def get_prices():
    """Get current prices for all assets."""
    try:
        prices = price_updater.get_all_prices()
        
        return jsonify({
            "prices": prices,
            "timestamp": datetime.utcnow().isoformat(),
            "count": len(prices)
        })
        
    except Exception as e:
        logger.error(f"Error getting prices: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@realtime_bp.route('/prices/<asset_symbol>')
def get_price(asset_symbol: str):
    """Get current price for specific asset."""
    try:
        price_data = price_updater.get_price(asset_symbol)
        
        if not price_data:
            return jsonify({
                "error": f"Price data not found for {asset_symbol}",
                "timestamp": datetime.utcnow().isoformat()
            }), 404
        
        return jsonify({
            "asset_symbol": asset_symbol,
            "price_data": price_data,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting price for {asset_symbol}: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@realtime_bp.route('/prices/start', methods=['POST'])
def start_price_updates():
    """Start real-time price updates."""
    try:
        data = request.get_json()
        asset_ids = data.get('asset_ids')  # Optional list of asset IDs
        
        # Start price updates
        asyncio.run_coroutine_threadsafe(
            price_updater.start_price_updates(asset_ids),
            asyncio.new_event_loop()
        )
        
        return jsonify({
            "message": "Price updates started",
            "asset_ids": asset_ids or "all",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error starting price updates: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@realtime_bp.route('/prices/stats')
def get_price_stats():
    """Get price update statistics."""
    try:
        stats = price_updater.get_update_stats()
        
        return jsonify({
            "stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting price stats: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@realtime_bp.route('/prices/history/<asset_symbol>')
def get_price_history(asset_symbol: str):
    """Get recent price history for an asset."""
    try:
        # Get parameters
        hours = request.args.get('hours', 24, type=int)
        limit = request.args.get('limit', 100, type=int)
        
        container = get_container()
        quote_repo = container.quote_repository()
        asset_repo = container.asset_repository()
        
        # Get asset
        asset = asset_repo.get_by_symbol(asset_symbol)
        if not asset:
            return jsonify({
                "error": f"Asset {asset_symbol} not found",
                "timestamp": datetime.utcnow().isoformat()
            }), 404
        
        # Get historical quotes
        start_date = datetime.utcnow() - timedelta(hours=hours)
        quotes = quote_repo.get_by_asset_and_date_range(asset.id, start_date, datetime.utcnow())
        
        # Convert to list
        history = []
        for quote in quotes[:limit]:
            history.append({
                "timestamp": quote.timestamp.isoformat(),
                "open": quote.open,
                "high": quote.high,
                "low": quote.low,
                "close": quote.close,
                "volume": quote.volume
            })
        
        return jsonify({
            "asset_symbol": asset_symbol,
            "history": history,
            "period_hours": hours,
            "count": len(history),
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting price history for {asset_symbol}: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@realtime_bp.route('/alerts')
def get_price_alerts():
    """Get recent price alerts."""
    try:
        hours = request.args.get('hours', 1, type=int)
        
        # Get alerts from cache
        cache = get_cache()
        alert_keys = cache.keys("price_alert:*")
        
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
        logger.error(f"Error getting price alerts: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@realtime_bp.route('/health')
def realtime_health():
    """Health check for real-time services."""
    try:
        stats = price_updater.get_update_stats()
        
        health = {
            "status": "healthy",
            "price_updater": {
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
        logger.error(f"Error in realtime health check: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500
