"""
Customizable dashboards API for advanced UI features.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
from flask import Blueprint, request, jsonify
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache
from app.infrastructure.metrics import get_metrics
from app.infrastructure.risk_analytics import get_risk_analytics
from app.infrastructure.market_intelligence import get_market_intelligence
from app.container import get_container

logger = logging.getLogger(__name__)

# Create Blueprint
dashboards_bp = Blueprint('dashboards', __name__, url_prefix='/api/dashboards')


class WidgetType(Enum):
    """Dashboard widget types."""
    CHART = "chart"
    TABLE = "table"
    METRIC = "metric"
    ALERT = "alert"
    NEWS = "news"
    SENTIMENT = "sentiment"
    ECONOMIC_CALENDAR = "economic_calendar"
    PORTFOLIO_SUMMARY = "portfolio_summary"
    RISK_METRICS = "risk_metrics"
    PERFORMANCE_CHART = "performance_chart"


class ChartType(Enum):
    """Chart types for widgets."""
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    SCATTER = "scatter"
    CANDLESTICK = "candlestick"
    HEATMAP = "heatmap"
    HISTOGRAM = "histogram"
    AREA = "area"


@dataclass
class WidgetConfig:
    """Dashboard widget configuration."""
    widget_id: str
    widget_type: WidgetType
    title: str
    position: Dict[str, int]  # x, y, width, height
    data_source: str
    chart_type: Optional[ChartType] = None
    config: Dict[str, Any] = None
    refresh_interval: int = 300  # seconds
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['widget_type'] = self.widget_type.value
        if self.chart_type:
            result['chart_type'] = self.chart_type.value
        if self.config is None:
            result['config'] = {}
        return result


@dataclass
class DashboardConfig:
    """Dashboard configuration."""
    dashboard_id: str
    name: str
    description: str
    user_id: str
    layout: Dict[str, Any]  # grid layout configuration
    widgets: List[WidgetConfig]
    theme: str = "light"
    created_at: datetime
    updated_at: datetime
    is_public: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['widgets'] = [widget.to_dict() for widget in self.widgets]
        result['created_at'] = self.created_at.isoformat()
        result['updated_at'] = self.updated_at.isoformat()
        return result


class DashboardManager(LoggerMixin):
    """Dashboard management system."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.container = get_container()
        self.risk_analytics = get_risk_analytics()
        self.market_intelligence = get_market_intelligence()
        
        # In-memory storage (in production, use database)
        self.dashboards = {}
        self.widget_templates = self._initialize_widget_templates()
    
    def _initialize_widget_templates(self) -> Dict[str, WidgetConfig]:
        """Initialize default widget templates."""
        templates = {}
        
        # Portfolio summary widget
        templates["portfolio_summary"] = WidgetConfig(
            widget_id="portfolio_summary",
            widget_type=WidgetType.PORTFOLIO_SUMMARY,
            title="Portfolio Summary",
            position={"x": 0, "y": 0, "width": 6, "height": 4},
            data_source="portfolio",
            refresh_interval=60
        )
        
        # Risk metrics widget
        templates["risk_metrics"] = WidgetConfig(
            widget_id="risk_metrics",
            widget_type=WidgetType.RISK_METRICS,
            title="Risk Metrics",
            position={"x": 6, "y": 0, "width": 6, "height": 4},
            data_source="risk",
            refresh_interval=300
        )
        
        # Performance chart widget
        templates["performance_chart"] = WidgetConfig(
            widget_id="performance_chart",
            widget_type=WidgetType.PERFORMANCE_CHART,
            title="Performance Chart",
            position={"x": 0, "y": 4, "width": 12, "height": 6},
            data_source="performance",
            chart_type=ChartType.LINE,
            config={"period": "1M"},
            refresh_interval=300
        )
        
        # Economic calendar widget
        templates["economic_calendar"] = WidgetConfig(
            widget_id="economic_calendar",
            widget_type=WidgetType.ECONOMIC_CALENDAR,
            title="Economic Calendar",
            position={"x": 0, "y": 10, "width": 12, "height": 4},
            data_source="economic",
            refresh_interval=3600
        )
        
        # Sentiment widget
        templates["sentiment"] = WidgetConfig(
            widget_id="sentiment",
            widget_type=WidgetType.SENTIMENT,
            title="Market Sentiment",
            position={"x": 0, "y": 14, "width": 6, "height": 4},
            data_source="sentiment",
            refresh_interval=1800
        )
        
        # News widget
        templates["news"] = WidgetConfig(
            widget_id="news",
            widget_type=WidgetType.NEWS,
            title="Latest News",
            position={"x": 6, "y": 14, "width": 6, "height": 4},
            data_source="news",
            refresh_interval=600
        )
        
        return templates
    
    def create_dashboard(self, name: str, user_id: str, description: str = "",
                        widgets: List[str] = None) -> str:
        """Create a new dashboard."""
        try:
            import uuid
            
            dashboard_id = str(uuid.uuid4())
            
            # Use default widgets if none specified
            if widgets is None:
                widgets = ["portfolio_summary", "risk_metrics", "performance_chart", "economic_calendar"]
            
            # Create widget configurations
            widget_configs = []
            for i, widget_name in enumerate(widgets):
                if widget_name in self.widget_templates:
                    template = self.widget_templates[widget_name]
                    # Adjust position for grid layout
                    widget_config = WidgetConfig(
                        widget_id=f"{template.widget_id}_{dashboard_id}",
                        widget_type=template.widget_type,
                        title=template.title,
                        position=template.position,
                        data_source=template.data_source,
                        chart_type=template.chart_type,
                        config=template.config,
                        refresh_interval=template.refresh_interval
                    )
                    widget_configs.append(widget_config)
            
            # Create dashboard
            dashboard = DashboardConfig(
                dashboard_id=dashboard_id,
                name=name,
                description=description,
                user_id=user_id,
                layout={"cols": 12, "rows": 18},
                widgets=widget_configs,
                theme="light",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                is_public=False
            )
            
            self.dashboards[dashboard_id] = dashboard
            
            self.logger.info(f"Created dashboard {dashboard_id} for user {user_id}")
            
            # Record metrics
            self.metrics.record_trading_signal(
                signal_type="dashboard_created",
                asset_symbol=dashboard_id
            )
            
            return dashboard_id
            
        except Exception as e:
            self.logger.error(f"Error creating dashboard: {e}")
            raise
    
    def get_dashboard(self, dashboard_id: str) -> Optional[DashboardConfig]:
        """Get dashboard configuration."""
        try:
            return self.dashboards.get(dashboard_id)
        except Exception as e:
            self.logger.error(f"Error getting dashboard: {e}")
            return None
    
    def update_dashboard(self, dashboard_id: str, updates: Dict[str, Any]) -> bool:
        """Update dashboard configuration."""
        try:
            if dashboard_id not in self.dashboards:
                return False
            
            dashboard = self.dashboards[dashboard_id]
            
            # Update allowed fields
            if "name" in updates:
                dashboard.name = updates["name"]
            if "description" in updates:
                dashboard.description = updates["description"]
            if "theme" in updates:
                dashboard.theme = updates["theme"]
            if "layout" in updates:
                dashboard.layout = updates["layout"]
            if "widgets" in updates:
                # Update widget configurations
                new_widgets = []
                for widget_data in updates["widgets"]:
                    widget = WidgetConfig(**widget_data)
                    new_widgets.append(widget)
                dashboard.widgets = new_widgets
            
            dashboard.updated_at = datetime.utcnow()
            
            # Clear cache for this dashboard
            cache_key = f"dashboard_data:{dashboard_id}"
            self.cache.delete(cache_key)
            
            self.logger.info(f"Updated dashboard {dashboard_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating dashboard: {e}")
            return False
    
    def delete_dashboard(self, dashboard_id: str) -> bool:
        """Delete a dashboard."""
        try:
            if dashboard_id not in self.dashboards:
                return False
            
            del self.dashboards[dashboard_id]
            
            # Clear cache
            cache_key = f"dashboard_data:{dashboard_id}"
            self.cache.delete(cache_key)
            
            self.logger.info(f"Deleted dashboard {dashboard_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting dashboard: {e}")
            return False
    
    def get_user_dashboards(self, user_id: str) -> List[DashboardConfig]:
        """Get all dashboards for a user."""
        try:
            return [dashboard for dashboard in self.dashboards.values() 
                   if dashboard.user_id == user_id]
        except Exception as e:
            self.logger.error(f"Error getting user dashboards: {e}")
            return []
    
    async def get_dashboard_data(self, dashboard_id: str) -> Dict[str, Any]:
        """Get data for all widgets in a dashboard."""
        try:
            # Check cache first
            cache_key = f"dashboard_data:{dashboard_id}"
            cached_data = self.cache.get(cache_key)
            if cached_data:
                return cached_data
            
            dashboard = self.get_dashboard(dashboard_id)
            if not dashboard:
                return {"error": "Dashboard not found"}
            
            widget_data = {}
            
            for widget in dashboard.widgets:
                try:
                    data = await self._get_widget_data(widget)
                    widget_data[widget.widget_id] = data
                except Exception as e:
                    self.logger.error(f"Error getting data for widget {widget.widget_id}: {e}")
                    widget_data[widget.widget_id] = {"error": str(e)}
            
            dashboard_data = {
                "dashboard_id": dashboard_id,
                "dashboard_name": dashboard.name,
                "theme": dashboard.theme,
                "widgets": widget_data,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Cache results
            self.cache.set(cache_key, dashboard_data, ttl=300)  # 5 minutes
            
            return dashboard_data
            
        except Exception as e:
            self.logger.error(f"Error getting dashboard data: {e}")
            return {"error": str(e)}
    
    async def _get_widget_data(self, widget: WidgetConfig) -> Dict[str, Any]:
        """Get data for a specific widget."""
        try:
            if widget.widget_type == WidgetType.PORTFOLIO_SUMMARY:
                return await self._get_portfolio_summary_data(widget)
            elif widget.widget_type == WidgetType.RISK_METRICS:
                return await self._get_risk_metrics_data(widget)
            elif widget.widget_type == WidgetType.PERFORMANCE_CHART:
                return await self._get_performance_chart_data(widget)
            elif widget.widget_type == WidgetType.ECONOMIC_CALENDAR:
                return await self._get_economic_calendar_data(widget)
            elif widget.widget_type == WidgetType.SENTIMENT:
                return await self._get_sentiment_data(widget)
            elif widget.widget_type == WidgetType.NEWS:
                return await self._get_news_data(widget)
            elif widget.widget_type == WidgetType.CHART:
                return await self._get_chart_data(widget)
            elif widget.widget_type == WidgetType.METRIC:
                return await self._get_metric_data(widget)
            else:
                return {"error": f"Unsupported widget type: {widget.widget_type}"}
        
        except Exception as e:
            self.logger.error(f"Error getting widget data: {e}")
            return {"error": str(e)}
    
    async def _get_portfolio_summary_data(self, widget: WidgetConfig) -> Dict[str, Any]:
        """Get portfolio summary data."""
        try:
            # Mock portfolio data - in production, get from actual portfolio
            portfolio_data = {
                "total_value": 100000,
                "total_pnl": 5000,
                "pnl_percent": 5.0,
                "positions": [
                    {"symbol": "AAPL", "value": 25000, "pnl": 1500, "pnl_percent": 6.0},
                    {"symbol": "MSFT", "value": 20000, "pnl": 800, "pnl_percent": 4.2},
                    {"symbol": "GOOGL", "value": 15000, "pnl": -300, "pnl_percent": -2.0},
                    {"symbol": "AMZN", "value": 18000, "pnl": 1200, "pnl_percent": 7.1},
                    {"symbol": "TSLA", "value": 22000, "pnl": 1800, "pnl_percent": 8.9}
                ],
                "cash": 0,
                "last_updated": datetime.utcnow().isoformat()
            }
            
            # Create pie chart
            fig = go.Figure(data=[go.Pie(
                labels=[pos["symbol"] for pos in portfolio_data["positions"]],
                values=[pos["value"] for pos in portfolio_data["positions"]],
                title="Portfolio Composition"
            )])
            
            portfolio_data["chart"] = fig.to_html(include_plotlyjs='cdn')
            
            return portfolio_data
            
        except Exception as e:
            self.logger.error(f"Error getting portfolio summary: {e}")
            return {"error": str(e)}
    
    async def _get_risk_metrics_data(self, widget: WidgetConfig) -> Dict[str, Any]:
        """Get risk metrics data."""
        try:
            # Mock risk metrics - in production, calculate from actual portfolio
            risk_data = {
                "portfolio_var": 2500,
                "max_drawdown": -8.5,
                "sharpe_ratio": 1.2,
                "beta": 1.1,
                "volatility": 0.18,
                "diversification_score": 0.75,
                "concentration_risk": 0.35,
                "risk_level": "MEDIUM",
                "risk_assessment": "Portfolio risk is within acceptable limits",
                "recommendations": [
                    "Consider diversifying to reduce concentration risk",
                    "Monitor volatility levels",
                    "Review position sizes"
                ],
                "last_updated": datetime.utcnow().isoformat()
            }
            
            # Create risk gauge chart
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=risk_data["sharpe_ratio"],
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Sharpe Ratio"},
                gauge={
                    'axis': {'range': [None, 3]},
                    'bar': {'color': "darkblue"},
                    'steps': [
                        {'range': [0, 1], 'color': "lightgray"},
                        {'range': [1, 2], 'color': "gray"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 2.5
                    }
                }
            ))
            
            risk_data["chart"] = fig.to_html(include_plotlyjs='cdn')
            
            return risk_data
            
        except Exception as e:
            self.logger.error(f"Error getting risk metrics: {e}")
            return {"error": str(e)}
    
    async def _get_performance_chart_data(self, widget: WidgetConfig) -> Dict[str, Any]:
        """Get performance chart data."""
        try:
            # Generate mock performance data
            dates = pd.date_range(end=datetime.utcnow(), periods=30, freq='D')
            
            # Generate random walk with upward trend
            returns = np.random.normal(0.001, 0.02, len(dates))
            cumulative_returns = np.cumprod(1 + returns)
            
            performance_data = {
                "dates": dates.strftime('%Y-%m-%d').tolist(),
                "portfolio_value": (cumulative_returns * 100000).tolist(),
                "benchmark_value": (cumulative_returns * 100000 * 0.95).tolist(),  # Underperforming benchmark
                "period": widget.config.get("period", "1M"),
                "total_return": (cumulative_returns[-1] - 1) * 100,
                "annualized_return": ((cumulative_returns[-1] ** (252/len(dates))) - 1) * 100,
                "volatility": np.std(returns) * np.sqrt(252),
                "last_updated": datetime.utcnow().isoformat()
            }
            
            # Create performance chart
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=performance_data["dates"],
                y=performance_data["portfolio_value"],
                mode='lines',
                name='Portfolio',
                line=dict(color='blue')
            ))
            fig.add_trace(go.Scatter(
                x=performance_data["dates"],
                y=performance_data["benchmark_value"],
                mode='lines',
                name='Benchmark',
                line=dict(color='red', dash='dash')
            ))
            
            fig.update_layout(
                title=f"Portfolio Performance ({performance_data['period']})",
                xaxis_title="Date",
                yaxis_title="Portfolio Value ($)",
                hovermode='x unified'
            )
            
            performance_data["chart"] = fig.to_html(include_plotlyjs='cdn')
            
            return performance_data
            
        except Exception as e:
            self.logger.error(f"Error getting performance chart: {e}")
            return {"error": str(e)}
    
    async def _get_economic_calendar_data(self, widget: WidgetConfig) -> Dict[str, Any]:
        """Get economic calendar data."""
        try:
            # Get economic events
            intelligence = await self.market_intelligence.get_comprehensive_intelligence(days_ahead=7)
            
            economic_events = intelligence.get("economic_intelligence", {}).get("events", [])
            impact_analysis = intelligence.get("economic_intelligence", {}).get("impact_analysis", {})
            
            calendar_data = {
                "events": economic_events[:10],  # Top 10 events
                "impact_analysis": impact_analysis,
                "upcoming_high_impact": impact_analysis.get("upcoming_high_impact", []),
                "last_updated": datetime.utcnow().isoformat()
            }
            
            return calendar_data
            
        except Exception as e:
            self.logger.error(f"Error getting economic calendar: {e}")
            return {"error": str(e)}
    
    async def _get_sentiment_data(self, widget: WidgetConfig) -> Dict[str, Any]:
        """Get sentiment data."""
        try:
            # Get sentiment for major indices
            symbols = ["SPY", "QQQ", "DIA"]
            sentiment_data = {}
            
            for symbol in symbols:
                intelligence = await self.market_intelligence.get_comprehensive_intelligence([symbol])
                sentiment_info = intelligence.get("sentiment_intelligence", {}).get(symbol, {})
                sentiment_data[symbol] = sentiment_info
            
            # Create sentiment chart
            if sentiment_data:
                symbols_list = list(sentiment_data.keys())
                sentiments = [data.get("current_sentiment", 0) for data in sentiment_data.values()]
                
                fig = go.Figure(data=[
                    go.Bar(
                        x=symbols_list,
                        y=sentiments,
                        marker_color=['green' if s > 0 else 'red' for s in sentiments]
                    )
                ])
                
                fig.update_layout(
                    title="Market Sentiment",
                    xaxis_title="Symbol",
                    yaxis_title="Sentiment Score"
                )
                
                chart_html = fig.to_html(include_plotlyjs='cdn')
            else:
                chart_html = ""
            
            return {
                "sentiment_data": sentiment_data,
                "chart": chart_html,
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting sentiment data: {e}")
            return {"error": str(e)}
    
    async def _get_news_data(self, widget: WidgetConfig) -> Dict[str, Any]:
        """Get latest news data."""
        try:
            # Mock news data - in production, integrate with news API
            news_data = {
                "articles": [
                    {
                        "title": "Fed Signals Potential Rate Pause Amid Economic Uncertainty",
                        "source": "Reuters",
                        "timestamp": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                        "sentiment": "neutral",
                        "summary": "Federal Reserve officials indicated they may pause interest rate hikes..."
                    },
                    {
                        "title": "Tech Stocks Rally on AI Optimism",
                        "source": "Bloomberg",
                        "timestamp": (datetime.utcnow() - timedelta(hours=4)).isoformat(),
                        "sentiment": "positive",
                        "summary": "Technology stocks surged today driven by optimism around artificial intelligence..."
                    },
                    {
                        "title": "Oil Prices Drop on Demand Concerns",
                        "source": "CNBC",
                        "timestamp": (datetime.utcnow() - timedelta(hours=6)).isoformat(),
                        "sentiment": "negative",
                        "summary": "Crude oil prices fell sharply as investors worried about global demand..."
                    }
                ],
                "last_updated": datetime.utcnow().isoformat()
            }
            
            return news_data
            
        except Exception as e:
            self.logger.error(f"Error getting news data: {e}")
            return {"error": str(e)}
    
    async def _get_chart_data(self, widget: WidgetConfig) -> Dict[str, Any]:
        """Get generic chart data."""
        try:
            # Generate mock chart data based on chart type
            if widget.chart_type == ChartType.LINE:
                return await self._generate_line_chart(widget)
            elif widget.chart_type == ChartType.BAR:
                return await self._generate_bar_chart(widget)
            elif widget.chart_type == ChartType.PIE:
                return await self._generate_pie_chart(widget)
            else:
                return {"error": f"Unsupported chart type: {widget.chart_type}"}
        
        except Exception as e:
            self.logger.error(f"Error getting chart data: {e}")
            return {"error": str(e)}
    
    async def _generate_line_chart(self, widget: WidgetConfig) -> Dict[str, Any]:
        """Generate line chart data."""
        try:
            dates = pd.date_range(end=datetime.utcnow(), periods=30, freq='D')
            values = np.random.normal(100, 10, len(dates))
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=dates.strftime('%Y-%m-%d').tolist(),
                y=values.tolist(),
                mode='lines',
                name=widget.title
            ))
            
            fig.update_layout(
                title=widget.title,
                xaxis_title="Date",
                yaxis_title="Value"
            )
            
            return {
                "chart": fig.to_html(include_plotlyjs='cdn'),
                "data": {
                    "dates": dates.strftime('%Y-%m-%d').tolist(),
                    "values": values.tolist()
                },
                "chart_type": "line",
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error generating line chart: {e}")
            return {"error": str(e)}
    
    async def _generate_bar_chart(self, widget: WidgetConfig) -> Dict[str, Any]:
        """Generate bar chart data."""
        try:
            categories = ["Category A", "Category B", "Category C", "Category D", "Category E"]
            values = np.random.randint(10, 100, len(categories))
            
            fig = go.Figure(data=[
                go.Bar(x=categories, y=values)
            ])
            
            fig.update_layout(
                title=widget.title,
                xaxis_title="Category",
                yaxis_title="Value"
            )
            
            return {
                "chart": fig.to_html(include_plotlyjs='cdn'),
                "data": {
                    "categories": categories,
                    "values": values.tolist()
                },
                "chart_type": "bar",
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error generating bar chart: {e}")
            return {"error": str(e)}
    
    async def _generate_pie_chart(self, widget: WidgetConfig) -> Dict[str, Any]:
        """Generate pie chart data."""
        try:
            labels = ["Segment A", "Segment B", "Segment C", "Segment D"]
            values = np.random.randint(10, 50, len(labels))
            
            fig = go.Figure(data=[go.Pie(labels=labels, values=values)])
            
            return {
                "chart": fig.to_html(include_plotlyjs='cdn'),
                "data": {
                    "labels": labels,
                    "values": values.tolist()
                },
                "chart_type": "pie",
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error generating pie chart: {e}")
            return {"error": str(e)}
    
    async def _get_metric_data(self, widget: WidgetConfig) -> Dict[str, Any]:
        """Get metric data."""
        try:
            # Generate mock metric data
            metric_value = np.random.uniform(0, 100)
            
            return {
                "value": metric_value,
                "unit": widget.config.get("unit", ""),
                "trend": np.random.choice(["up", "down", "stable"]),
                "change": np.random.uniform(-10, 10),
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting metric data: {e}")
            return {"error": str(e)}


# Global instance
dashboard_manager = DashboardManager()


def get_dashboard_manager() -> DashboardManager:
    """Get dashboard manager instance."""
    return dashboard_manager


# API Routes
@dashboards_bp.route('/dashboards', methods=['POST'])
def create_dashboard():
    """Create a new dashboard."""
    try:
        data = request.get_json()
        
        name = data.get('name')
        user_id = data.get('user_id', 'default_user')
        description = data.get('description', '')
        widgets = data.get('widgets')
        
        if not name:
            return jsonify({"error": "Name is required"}), 400
        
        dashboard_id = dashboard_manager.create_dashboard(name, user_id, description, widgets)
        
        return jsonify({
            "dashboard_id": dashboard_id,
            "message": "Dashboard created successfully"
        })
        
    except Exception as e:
        logger.error(f"Error creating dashboard: {e}")
        return jsonify({"error": str(e)}), 500


@dashboards_bp.route('/dashboards/<dashboard_id>', methods=['GET'])
def get_dashboard(dashboard_id: str):
    """Get dashboard configuration."""
    try:
        dashboard = dashboard_manager.get_dashboard(dashboard_id)
        
        if not dashboard:
            return jsonify({"error": "Dashboard not found"}), 404
        
        return jsonify(dashboard.to_dict())
        
    except Exception as e:
        logger.error(f"Error getting dashboard: {e}")
        return jsonify({"error": str(e)}), 500


@dashboards_bp.route('/dashboards/<dashboard_id>', methods=['PUT'])
def update_dashboard(dashboard_id: str):
    """Update dashboard configuration."""
    try:
        data = request.get_json()
        
        success = dashboard_manager.update_dashboard(dashboard_id, data)
        
        if not success:
            return jsonify({"error": "Dashboard not found or update failed"}), 404
        
        return jsonify({"message": "Dashboard updated successfully"})
        
    except Exception as e:
        logger.error(f"Error updating dashboard: {e}")
        return jsonify({"error": str(e)}), 500


@dashboards_bp.route('/dashboards/<dashboard_id>', methods=['DELETE'])
def delete_dashboard(dashboard_id: str):
    """Delete a dashboard."""
    try:
        success = dashboard_manager.delete_dashboard(dashboard_id)
        
        if not success:
            return jsonify({"error": "Dashboard not found"}), 404
        
        return jsonify({"message": "Dashboard deleted successfully"})
        
    except Exception as e:
        logger.error(f"Error deleting dashboard: {e}")
        return jsonify({"error": str(e)}), 500


@dashboards_bp.route('/dashboards/user/<user_id>', methods=['GET'])
def get_user_dashboards(user_id: str):
    """Get all dashboards for a user."""
    try:
        dashboards = dashboard_manager.get_user_dashboards(user_id)
        
        return jsonify({
            "dashboards": [dashboard.to_dict() for dashboard in dashboards]
        })
        
    except Exception as e:
        logger.error(f"Error getting user dashboards: {e}")
        return jsonify({"error": str(e)}), 500


@dashboards_bp.route('/dashboards/<dashboard_id>/data', methods=['GET'])
async def get_dashboard_data(dashboard_id: str):
    """Get data for a dashboard."""
    try:
        data = await dashboard_manager.get_dashboard_data(dashboard_id)
        
        return jsonify(data)
        
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        return jsonify({"error": str(e)}), 500


@dashboards_bp.route('/dashboards/templates', methods=['GET'])
def get_widget_templates():
    """Get available widget templates."""
    try:
        templates = {
            name: template.to_dict() 
            for name, template in dashboard_manager.widget_templates.items()
        }
        
        return jsonify({"templates": templates})
        
    except Exception as e:
        logger.error(f"Error getting widget templates: {e}")
        return jsonify({"error": str(e)}), 500


@dashboards_bp.route('/dashboards/widgets/<widget_id>/data', methods=['GET'])
async def get_widget_data(widget_id: str):
    """Get data for a specific widget."""
    try:
        # Find widget in any dashboard
        widget = None
        for dashboard in dashboard_manager.dashboards.values():
            for w in dashboard.widgets:
                if w.widget_id == widget_id:
                    widget = w
                    break
            if widget:
                break
        
        if not widget:
            return jsonify({"error": "Widget not found"}), 404
        
        data = await dashboard_manager._get_widget_data(widget)
        
        return jsonify(data)
        
    except Exception as e:
        logger.error(f"Error getting widget data: {e}")
        return jsonify({"error": str(e)}), 500
