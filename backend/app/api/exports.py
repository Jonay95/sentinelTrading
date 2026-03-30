"""
Export functionality for CSV, PDF, and other formats.
"""

import logging
import csv
import io
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
from flask import Blueprint, request, jsonify, send_file
import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.lineplots import HorizontalLineChart
from reportlab.graphics.charts.barcharts import VerticalBarChart
import plotly.graph_objects as go
import plotly.express as px
import numpy as np

from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache
from app.infrastructure.metrics import get_metrics
from app.container import get_container

logger = logging.getLogger(__name__)

# Create Blueprint
exports_bp = Blueprint('exports', __name__, url_prefix='/api/exports')


class ExportFormat(Enum):
    """Export formats."""
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"
    JSON = "json"
    HTML = "html"


class ExportType(Enum):
    """Export types."""
    PORTFOLIO_DATA = "portfolio_data"
    TRANSACTIONS = "transactions"
    PERFORMANCE_REPORT = "performance_report"
    RISK_ANALYSIS = "risk_analysis"
    MARKET_DATA = "market_data"
    ALERTS = "alerts"
    DASHBOARD = "dashboard"


@dataclass
class ExportConfig:
    """Export configuration."""
    export_type: ExportType
    format: ExportFormat
    date_range: Dict[str, str]  # start_date, end_date
    symbols: List[str] = None
    include_charts: bool = True
    include_summary: bool = True
    template: str = "default"  # For PDF templates
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['export_type'] = self.export_type.value
        result['format'] = self.format.value
        return result


class ExportManager(LoggerMixin):
    """Export functionality manager."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.container = get_container()
    
    def export_portfolio_data(self, config: ExportConfig) -> bytes:
        """Export portfolio data."""
        try:
            # Get portfolio data
            portfolio_data = self._get_portfolio_data(config)
            
            if config.format == ExportFormat.CSV:
                return self._export_to_csv(portfolio_data, config)
            elif config.format == ExportFormat.EXCEL:
                return self._export_to_excel(portfolio_data, config)
            elif config.format == ExportFormat.PDF:
                return self._export_to_pdf(portfolio_data, config)
            elif config.format == ExportFormat.JSON:
                return self._export_to_json(portfolio_data, config)
            elif config.format == ExportFormat.HTML:
                return self._export_to_html(portfolio_data, config)
            else:
                raise ValueError(f"Unsupported format: {config.format}")
        
        except Exception as e:
            self.logger.error(f"Error exporting portfolio data: {e}")
            raise
    
    def export_transactions(self, config: ExportConfig) -> bytes:
        """Export transactions data."""
        try:
            # Get transactions data
            transactions_data = self._get_transactions_data(config)
            
            if config.format == ExportFormat.CSV:
                return self._export_to_csv(transactions_data, config)
            elif config.format == ExportFormat.EXCEL:
                return self._export_to_excel(transactions_data, config)
            elif config.format == ExportFormat.PDF:
                return self._export_to_pdf(transactions_data, config)
            elif config.format == ExportFormat.JSON:
                return self._export_to_json(transactions_data, config)
            elif config.format == ExportFormat.HTML:
                return self._export_to_html(transactions_data, config)
            else:
                raise ValueError(f"Unsupported format: {config.format}")
        
        except Exception as e:
            self.logger.error(f"Error exporting transactions: {e}")
            raise
    
    def export_performance_report(self, config: ExportConfig) -> bytes:
        """Export performance report."""
        try:
            # Get performance data
            performance_data = self._get_performance_data(config)
            
            if config.format == ExportFormat.CSV:
                return self._export_to_csv(performance_data, config)
            elif config.format == ExportFormat.EXCEL:
                return self._export_to_excel(performance_data, config)
            elif config.format == ExportFormat.PDF:
                return self._export_performance_to_pdf(performance_data, config)
            elif config.format == ExportFormat.JSON:
                return self._export_to_json(performance_data, config)
            elif config.format == ExportFormat.HTML:
                return self._export_performance_to_html(performance_data, config)
            else:
                raise ValueError(f"Unsupported format: {config.format}")
        
        except Exception as e:
            self.logger.error(f"Error exporting performance report: {e}")
            raise
    
    def export_risk_analysis(self, config: ExportConfig) -> bytes:
        """Export risk analysis."""
        try:
            # Get risk data
            risk_data = self._get_risk_data(config)
            
            if config.format == ExportFormat.CSV:
                return self._export_to_csv(risk_data, config)
            elif config.format == ExportFormat.EXCEL:
                return self._export_to_excel(risk_data, config)
            elif config.format == ExportFormat.PDF:
                return self._export_to_pdf(risk_data, config)
            elif config.format == ExportFormat.JSON:
                return self._export_to_json(risk_data, config)
            elif config.format == ExportFormat.HTML:
                return self._export_to_html(risk_data, config)
            else:
                raise ValueError(f"Unsupported format: {config.format}")
        
        except Exception as e:
            self.logger.error(f"Error exporting risk analysis: {e}")
            raise
    
    def export_market_data(self, config: ExportConfig) -> bytes:
        """Export market data."""
        try:
            # Get market data
            market_data = self._get_market_data(config)
            
            if config.format == ExportFormat.CSV:
                return self._export_to_csv(market_data, config)
            elif config.format == ExportFormat.EXCEL:
                return self._export_to_excel(market_data, config)
            elif config.format == ExportFormat.JSON:
                return self._export_to_json(market_data, config)
            elif config.format == ExportFormat.HTML:
                return self._export_to_html(market_data, config)
            else:
                raise ValueError(f"Unsupported format: {config.format}")
        
        except Exception as e:
            self.logger.error(f"Error exporting market data: {e}")
            raise
    
    def _get_portfolio_data(self, config: ExportConfig) -> Dict[str, Any]:
        """Get portfolio data for export."""
        try:
            # Mock portfolio data - in production, get from actual portfolio
            portfolio_data = {
                "summary": {
                    "total_value": 100000,
                    "total_pnl": 5000,
                    "pnl_percent": 5.0,
                    "cash": 0,
                    "last_updated": datetime.utcnow().isoformat()
                },
                "positions": [
                    {
                        "symbol": "AAPL",
                        "quantity": 100,
                        "entry_price": 150.0,
                        "current_price": 165.0,
                        "market_value": 16500,
                        "unrealized_pnl": 1500,
                        "pnl_percent": 10.0,
                        "weight": 0.165,
                        "sector": "Technology"
                    },
                    {
                        "symbol": "MSFT",
                        "quantity": 50,
                        "entry_price": 250.0,
                        "current_price": 260.0,
                        "market_value": 13000,
                        "unrealized_pnl": 500,
                        "pnl_percent": 4.0,
                        "weight": 0.13,
                        "sector": "Technology"
                    },
                    {
                        "symbol": "GOOGL",
                        "quantity": 30,
                        "entry_price": 2000.0,
                        "current_price": 1950.0,
                        "market_value": 58500,
                        "unrealized_pnl": -1500,
                        "pnl_percent": -2.5,
                        "weight": 0.585,
                        "sector": "Technology"
                    },
                    {
                        "symbol": "AMZN",
                        "quantity": 80,
                        "entry_price": 120.0,
                        "current_price": 125.0,
                        "market_value": 10000,
                        "unrealized_pnl": 400,
                        "pnl_percent": 4.2,
                        "weight": 0.10,
                        "sector": "Consumer Discretionary"
                    },
                    {
                        "symbol": "TSLA",
                        "quantity": 25,
                        "entry_price": 800.0,
                        "current_price": 860.0,
                        "market_value": 21500,
                        "unrealized_pnl": 1500,
                        "pnl_percent": 7.5,
                        "weight": 0.215,
                        "sector": "Automotive"
                    }
                ],
                "sector_allocation": {
                    "Technology": 0.78,
                    "Consumer Discretionary": 0.10,
                    "Automotive": 0.215
                }
            }
            
            return portfolio_data
        
        except Exception as e:
            self.logger.error(f"Error getting portfolio data: {e}")
            return {"error": str(e)}
    
    def _get_transactions_data(self, config: ExportConfig) -> Dict[str, Any]:
        """Get transactions data for export."""
        try:
            # Mock transactions data
            transactions_data = {
                "summary": {
                    "total_transactions": 25,
                    "total_volume": 1250000,
                    "total_commissions": 1250,
                    "date_range": config.date_range
                },
                "transactions": [
                    {
                        "transaction_id": "TXN001",
                        "symbol": "AAPL",
                        "action": "BUY",
                        "quantity": 100,
                        "price": 150.0,
                        "total_amount": 15000,
                        "commission": 15.0,
                        "timestamp": "2024-01-15T10:30:00Z",
                        "status": "COMPLETED"
                    },
                    {
                        "transaction_id": "TXN002",
                        "symbol": "MSFT",
                        "action": "BUY",
                        "quantity": 50,
                        "price": 250.0,
                        "total_amount": 12500,
                        "commission": 12.5,
                        "timestamp": "2024-01-16T14:20:00Z",
                        "status": "COMPLETED"
                    },
                    {
                        "transaction_id": "TXN003",
                        "symbol": "GOOGL",
                        "action": "BUY",
                        "quantity": 30,
                        "price": 2000.0,
                        "total_amount": 60000,
                        "commission": 60.0,
                        "timestamp": "2024-01-17T09:45:00Z",
                        "status": "COMPLETED"
                    },
                    {
                        "transaction_id": "TXN004",
                        "symbol": "AMZN",
                        "action": "BUY",
                        "quantity": 80,
                        "price": 120.0,
                        "total_amount": 9600,
                        "commission": 9.6,
                        "timestamp": "2024-01-18T11:15:00Z",
                        "status": "COMPLETED"
                    },
                    {
                        "transaction_id": "TXN005",
                        "symbol": "TSLA",
                        "action": "BUY",
                        "quantity": 25,
                        "price": 800.0,
                        "total_amount": 20000,
                        "commission": 20.0,
                        "timestamp": "2024-01-19T13:30:00Z",
                        "status": "COMPLETED"
                    }
                ]
            }
            
            return transactions_data
        
        except Exception as e:
            self.logger.error(f"Error getting transactions data: {e}")
            return {"error": str(e)}
    
    def _get_performance_data(self, config: ExportConfig) -> Dict[str, Any]:
        """Get performance data for export."""
        try:
            # Generate mock performance data
            dates = pd.date_range(end=datetime.utcnow(), periods=30, freq='D')
            
            performance_data = {
                "summary": {
                    "total_return": 5.0,
                    "annualized_return": 18.5,
                    "volatility": 0.18,
                    "sharpe_ratio": 1.2,
                    "max_drawdown": -8.5,
                    "calmar_ratio": 2.2,
                    "win_rate": 0.65,
                    "profit_factor": 1.8
                },
                "daily_returns": {
                    "dates": dates.strftime('%Y-%m-%d').tolist(),
                    "portfolio_values": [(1 + np.random.normal(0.001, 0.02, len(dates))).cumprod() * 100000].tolist(),
                    "benchmark_values": [(1 + np.random.normal(0.0008, 0.015, len(dates))).cumprod() * 100000].tolist()
                },
                "monthly_performance": [
                    {"month": "2024-01", "return": 2.5, "volatility": 0.15},
                    {"month": "2024-02", "return": 1.8, "volatility": 0.12},
                    {"month": "2024-03", "return": -0.5, "volatility": 0.18}
                ],
                "sector_performance": [
                    {"sector": "Technology", "return": 6.2, "weight": 0.78},
                    {"sector": "Consumer Discretionary", "return": 4.2, "weight": 0.10},
                    {"sector": "Automotive", "return": 7.5, "weight": 0.215}
                ]
            }
            
            return performance_data
        
        except Exception as e:
            self.logger.error(f"Error getting performance data: {e}")
            return {"error": str(e)}
    
    def _get_risk_data(self, config: ExportConfig) -> Dict[str, Any]:
        """Get risk data for export."""
        try:
            risk_data = {
                "summary": {
                    "portfolio_var": 2500,
                    "expected_shortfall": 3500,
                    "max_drawdown": -8.5,
                    "current_drawdown": -2.1,
                    "beta": 1.1,
                    "sharpe_ratio": 1.2,
                    "sortino_ratio": 1.8,
                    "calmar_ratio": 2.2,
                    "diversification_score": 0.75,
                    "concentration_risk": 0.35,
                    "correlation_risk": 0.65
                },
                "position_risks": [
                    {
                        "symbol": "AAPL",
                        "risk_amount": 1500,
                        "reward_amount": 3000,
                        "risk_reward_ratio": 2.0,
                        "var_95": -250,
                        "beta": 1.2,
                        "volatility": 0.22
                    },
                    {
                        "symbol": "MSFT",
                        "risk_amount": 625,
                        "reward_amount": 1250,
                        "risk_reward_ratio": 2.0,
                        "var_95": -125,
                        "beta": 0.9,
                        "volatility": 0.18
                    },
                    {
                        "symbol": "GOOGL",
                        "risk_amount": 4500,
                        "reward_amount": 6000,
                        "risk_reward_ratio": 1.33,
                        "var_95": -750,
                        "beta": 1.1,
                        "volatility": 0.25
                    }
                ],
                "risk_recommendations": [
                    "Consider diversifying to reduce concentration risk",
                    "Monitor volatility levels for high-beta positions",
                    "Review position sizes for better risk management"
                ]
            }
            
            return risk_data
        
        except Exception as e:
            self.logger.error(f"Error getting risk data: {e}")
            return {"error": str(e)}
    
    def _get_market_data(self, config: ExportConfig) -> Dict[str, Any]:
        """Get market data for export."""
        try:
            # Generate mock market data
            symbols = config.symbols or ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
            dates = pd.date_range(end=datetime.utcnow(), periods=30, freq='D')
            
            market_data = {
                "summary": {
                    "symbols": symbols,
                    "date_range": f"{dates[0].strftime('%Y-%m-%d')} to {dates[-1].strftime('%Y-%m-%d')}",
                    "total_data_points": len(symbols) * len(dates)
                },
                "price_data": {}
            }
            
            for symbol in symbols:
                # Generate price series
                base_price = np.random.uniform(100, 1000)
                prices = []
                
                for i in range(len(dates)):
                    if i == 0:
                        price = base_price
                    else:
                        # Random walk
                        change = np.random.normal(0, 0.02)
                        price = max(price * (1 + change), 1)
                    prices.append(price)
                
                market_data["price_data"][symbol] = {
                    "dates": dates.strftime('%Y-%m-%d').tolist(),
                    "prices": prices,
                    "open": prices[0],
                    "high": max(prices),
                    "low": min(prices),
                    "close": prices[-1],
                    "volume": np.random.randint(1000000, 10000000, len(dates)).tolist(),
                    "change": (prices[-1] - prices[0]) / prices[0] * 100,
                    "volatility": np.std(np.diff(prices)) * np.sqrt(252)
                }
            
            return market_data
        
        except Exception as e:
            self.logger.error(f"Error getting market data: {e}")
            return {"error": str(e)}
    
    def _export_to_csv(self, data: Dict[str, Any], config: ExportConfig) -> bytes:
        """Export data to CSV format."""
        try:
            output = io.StringIO()
            
            if config.export_type == ExportType.PORTFOLIO_DATA:
                writer = csv.writer(output)
                
                # Write summary
                writer.writerow(["Portfolio Summary"])
                for key, value in data["summary"].items():
                    writer.writerow([key, value])
                writer.writerow([])
                
                # Write positions
                writer.writerow(["Positions"])
                writer.writerow(["Symbol", "Quantity", "Entry Price", "Current Price", "Market Value", "P&L", "P&L %", "Weight", "Sector"])
                
                for position in data["positions"]:
                    writer.writerow([
                        position["symbol"],
                        position["quantity"],
                        position["entry_price"],
                        position["current_price"],
                        position["market_value"],
                        position["unrealized_pnl"],
                        position["pnl_percent"],
                        position["weight"],
                        position["sector"]
                    ])
            
            elif config.export_type == ExportType.TRANSACTIONS:
                writer = csv.writer(output)
                
                # Write summary
                writer.writerow(["Transaction Summary"])
                for key, value in data["summary"].items():
                    writer.writerow([key, value])
                writer.writerow([])
                
                # Write transactions
                writer.writerow(["Transactions"])
                writer.writerow(["ID", "Symbol", "Action", "Quantity", "Price", "Total", "Commission", "Timestamp", "Status"])
                
                for transaction in data["transactions"]:
                    writer.writerow([
                        transaction["transaction_id"],
                        transaction["symbol"],
                        transaction["action"],
                        transaction["quantity"],
                        transaction["price"],
                        transaction["total_amount"],
                        transaction["commission"],
                        transaction["timestamp"],
                        transaction["status"]
                    ])
            
            elif config.export_type == ExportType.MARKET_DATA:
                writer = csv.writer(output)
                
                # Write summary
                writer.writerow(["Market Data Summary"])
                for key, value in data["summary"].items():
                    writer.writerow([key, value])
                writer.writerow([])
                
                # Write price data for each symbol
                for symbol, symbol_data in data["price_data"].items():
                    writer.writerow([f"{symbol} Price Data"])
                    writer.writerow(["Date", "Price", "Volume"])
                    
                    for i in range(len(symbol_data["dates"])):
                        writer.writerow([
                            symbol_data["dates"][i],
                            symbol_data["prices"][i],
                            symbol_data["volume"][i]
                        ])
                    writer.writerow([])
            
            return output.getvalue().encode('utf-8')
        
        except Exception as e:
            self.logger.error(f"Error exporting to CSV: {e}")
            raise
    
    def _export_to_excel(self, data: Dict[str, Any], config: ExportConfig) -> bytes:
        """Export data to Excel format."""
        try:
            # Use pandas to create Excel file
            output = io.BytesIO()
            
            if config.export_type == ExportType.PORTFOLIO_DATA:
                # Create DataFrames
                summary_df = pd.DataFrame([data["summary"]]).T
                summary_df.columns = ["Value"]
                
                positions_df = pd.DataFrame(data["positions"])
                
                # Create Excel writer
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    summary_df.to_excel(writer, sheet_name='Summary', index=True)
                    positions_df.to_excel(writer, sheet_name='Positions', index=False)
            
            elif config.export_type == ExportType.TRANSACTIONS:
                summary_df = pd.DataFrame([data["summary"]]).T
                summary_df.columns = ["Value"]
                
                transactions_df = pd.DataFrame(data["transactions"])
                
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    summary_df.to_excel(writer, sheet_name='Summary', index=True)
                    transactions_df.to_excel(writer, sheet_name='Transactions', index=False)
            
            elif config.export_type == ExportType.MARKET_DATA:
                summary_df = pd.DataFrame([data["summary"]]).T
                summary_df.columns = ["Value"]
                
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    summary_df.to_excel(writer, sheet_name='Summary', index=True)
                    
                    # Create separate sheets for each symbol
                    for symbol, symbol_data in data["price_data"].items():
                        df = pd.DataFrame({
                            'Date': symbol_data["dates"],
                            'Price': symbol_data["prices"],
                            'Volume': symbol_data["volume"]
                        })
                        df.to_excel(writer, sheet_name=symbol, index=False)
            
            return output.getvalue()
        
        except Exception as e:
            self.logger.error(f"Error exporting to Excel: {e}")
            raise
    
    def _export_to_json(self, data: Dict[str, Any], config: ExportConfig) -> bytes:
        """Export data to JSON format."""
        try:
            return json.dumps(data, indent=2, default=str).encode('utf-8')
        
        except Exception as e:
            self.logger.error(f"Error exporting to JSON: {e}")
            raise
    
    def _export_to_html(self, data: Dict[str, Any], config: ExportConfig) -> bytes:
        """Export data to HTML format."""
        try:
            html_content = []
            html_content.append("<html><head><title>Export Report</title>")
            html_content.append("<style>")
            html_content.append("""
                body { font-family: Arial, sans-serif; margin: 20px; }
                table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                .summary { background-color: #f9f9f9; padding: 15px; margin-bottom: 20px; }
                h1 { color: #333; }
                h2 { color: #666; }
            """)
            html_content.append("</style></head><body>")
            
            if config.export_type == ExportType.PORTFOLIO_DATA:
                html_content.append("<h1>Portfolio Report</h1>")
                
                # Summary section
                html_content.append("<div class='summary'>")
                html_content.append("<h2>Summary</h2>")
                html_content.append("<table>")
                for key, value in data["summary"].items():
                    html_content.append(f"<tr><td><strong>{key}</strong></td><td>{value}</td></tr>")
                html_content.append("</table>")
                html_content.append("</div>")
                
                # Positions section
                html_content.append("<h2>Positions</h2>")
                html_content.append("<table>")
                html_content.append("<tr><th>Symbol</th><th>Quantity</th><th>Entry Price</th><th>Current Price</th><th>Market Value</th><th>P&L</th><th>P&L %</th><th>Weight</th><th>Sector</th></tr>")
                
                for position in data["positions"]:
                    html_content.append(f"<tr>")
                    html_content.append(f"<td>{position['symbol']}</td>")
                    html_content.append(f"<td>{position['quantity']}</td>")
                    html_content.append(f"<td>${position['entry_price']:.2f}</td>")
                    html_content.append(f"<td>${position['current_price']:.2f}</td>")
                    html_content.append(f"<td>${position['market_value']:,.2f}</td>")
                    html_content.append(f"<td>${position['unrealized_pnl']:,.2f}</td>")
                    html_content.append(f"<td>{position['pnl_percent']:.2f}%</td>")
                    html_content.append(f"<td>{position['weight']:.2%}</td>")
                    html_content.append(f"<td>{position['sector']}</td>")
                    html_content.append(f"</tr>")
                
                html_content.append("</table>")
            
            html_content.append("</body></html>")
            
            return "".join(html_content).encode('utf-8')
        
        except Exception as e:
            self.logger.error(f"Error exporting to HTML: {e}")
            raise
    
    def _export_to_pdf(self, data: Dict[str, Any], config: ExportConfig) -> bytes:
        """Export data to PDF format."""
        try:
            output = io.BytesIO()
            doc = SimpleDocTemplate(output, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                spaceAfter=30,
                alignment=1  # Center alignment
            )
            
            if config.export_type == ExportType.PORTFOLIO_DATA:
                story.append(Paragraph("Portfolio Report", title_style))
                
                # Summary section
                story.append(Paragraph("Summary", styles['Heading2']))
                
                summary_data = []
                for key, value in data["summary"].items():
                    summary_data.append([key, str(value)])
                
                summary_table = Table(summary_data)
                summary_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                story.append(summary_table)
                story.append(Spacer(1, 20))
                
                # Positions section
                story.append(Paragraph("Positions", styles['Heading2']))
                
                positions_data = [["Symbol", "Quantity", "Entry Price", "Current Price", "P&L", "P&L %", "Weight", "Sector"]]
                for position in data["positions"]:
                    positions_data.append([
                        position["symbol"],
                        str(position["quantity"]),
                        f"${position['entry_price']:.2f}",
                        f"${position['current_price']:.2f}",
                        f"${position['unrealized_pnl']:,.2f}",
                        f"{position['pnl_percent']:.2f}%",
                        f"{position['weight']:.2%}",
                        position["sector"]
                    ])
                
                positions_table = Table(positions_data)
                positions_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                story.append(positions_table)
            
            elif config.export_type == ExportType.TRANSACTIONS:
                story.append(Paragraph("Transaction Report", title_style))
                
                # Summary section
                story.append(Paragraph("Summary", styles['Heading2']))
                
                summary_data = []
                for key, value in data["summary"].items():
                    summary_data.append([key, str(value)])
                
                summary_table = Table(summary_data)
                summary_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                story.append(summary_table)
                story.append(Spacer(1, 20))
                
                # Transactions section
                story.append(Paragraph("Transactions", styles['Heading2']))
                
                transactions_data = [["ID", "Symbol", "Action", "Quantity", "Price", "Total", "Commission", "Timestamp", "Status"]]
                for transaction in data["transactions"]:
                    transactions_data.append([
                        transaction["transaction_id"],
                        transaction["symbol"],
                        transaction["action"],
                        str(transaction["quantity"]),
                        f"${transaction['price']:.2f}",
                        f"${transaction['total_amount']:,.2f}",
                        f"${transaction['commission']:.2f}",
                        transaction["timestamp"],
                        transaction["status"]
                    ])
                
                transactions_table = Table(transactions_data)
                transactions_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                story.append(transactions_table)
            
            # Build PDF
            doc.build(story)
            
            return output.getvalue()
        
        except Exception as e:
            self.logger.error(f"Error exporting to PDF: {e}")
            raise
    
    def _export_performance_to_pdf(self, data: Dict[str, Any], config: ExportConfig) -> bytes:
        """Export performance report to PDF format."""
        try:
            output = io.BytesIO()
            doc = SimpleDocTemplate(output, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                spaceAfter=30,
                alignment=1
            )
            
            story.append(Paragraph("Performance Report", title_style))
            
            # Summary section
            story.append(Paragraph("Performance Summary", styles['Heading2']))
            
            summary_data = []
            for key, value in data["summary"].items():
                if key != "daily_returns":  # Skip the large data array
                    summary_data.append([key.replace('_', ' ').title(), str(value)])
            
            summary_table = Table(summary_data)
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(summary_table)
            story.append(Spacer(1, 20))
            
            # Monthly performance
            story.append(Paragraph("Monthly Performance", styles['Heading2']))
            
            monthly_data = [["Month", "Return %", "Volatility"]]
            for month_data in data["monthly_performance"]:
                monthly_data.append([
                    month_data["month"],
                    f"{month_data['return']:.2f}%",
                    f"{month_data['volatility']:.2f}"
                ])
            
            monthly_table = Table(monthly_data)
            monthly_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(monthly_table)
            story.append(Spacer(1, 20))
            
            # Sector performance
            story.append(Paragraph("Sector Performance", styles['Heading2']))
            
            sector_data = [["Sector", "Return %", "Weight"]]
            for sector_data in data["sector_performance"]:
                sector_data.append([
                    sector_data["sector"],
                    f"{sector_data['return']:.2f}%",
                    f"{sector_data['weight']:.2%}"
                ])
            
            sector_table = Table(sector_data)
            sector_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(sector_table)
            
            # Build PDF
            doc.build(story)
            
            return output.getvalue()
        
        except Exception as e:
            self.logger.error(f"Error exporting performance to PDF: {e}")
            raise
    
    def _export_performance_to_html(self, data: Dict[str, Any], config: ExportConfig) -> bytes:
        """Export performance report to HTML format."""
        try:
            html_content = []
            html_content.append("<html><head><title>Performance Report</title>")
            html_content.append("<style>")
            html_content.append("""
                body { font-family: Arial, sans-serif; margin: 20px; }
                table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                .summary { background-color: #f9f9f9; padding: 15px; margin-bottom: 20px; }
                .chart { margin: 20px 0; }
                h1 { color: #333; }
                h2 { color: #666; }
            """)
            html_content.append("</style></head><body>")
            
            # Add Plotly.js for charts
            html_content.append("<script src='https://cdn.plot.ly/plotly-latest.min.js'></script>")
            
            html_content.append("<h1>Performance Report</h1>")
            
            # Summary section
            html_content.append("<div class='summary'>")
            html_content.append("<h2>Performance Summary</h2>")
            html_content.append("<table>")
            for key, value in data["summary"].items():
                if key != "daily_returns":  # Skip the large data array
                    html_content.append(f"<tr><td><strong>{key.replace('_', ' ').title()}</strong></td><td>{value}</td></tr>")
            html_content.append("</table>")
            html_content.append("</div>")
            
            # Performance chart
            if "daily_returns" in data:
                html_content.append("<h2>Performance Chart</h2>")
                html_content.append("<div id='performance-chart' class='chart'></div>")
                
                # Create chart using Plotly
                dates = data["daily_returns"]["dates"]
                portfolio_values = data["daily_returns"]["portfolio_values"]
                benchmark_values = data["daily_returns"]["benchmark_values"]
                
                chart_script = f"""
                <script>
                    var trace1 = {{
                        x: {dates},
                        y: {portfolio_values},
                        type: 'scatter',
                        mode: 'lines',
                        name: 'Portfolio'
                    }};
                    
                    var trace2 = {{
                        x: {dates},
                        y: {benchmark_values},
                        type: 'scatter',
                        mode: 'lines',
                        name: 'Benchmark'
                    }};
                    
                    var layout = {{
                        title: 'Portfolio Performance',
                        xaxis: {{ title: 'Date' }},
                        yaxis: {{ title: 'Portfolio Value ($)' }}
                    }};
                    
                    Plotly.newPlot('performance-chart', [trace1, trace2], layout);
                </script>
                """
                
                html_content.append(chart_script)
            
            # Monthly performance
            html_content.append("<h2>Monthly Performance</h2>")
            html_content.append("<table>")
            html_content.append("<tr><th>Month</th><th>Return %</th><th>Volatility</th></tr>")
            
            for month_data in data["monthly_performance"]:
                html_content.append(f"<tr>")
                html_content.append(f"<td>{month_data['month']}</td>")
                html_content.append(f"<td>{month_data['return']:.2f}%</td>")
                html_content.append(f"<td>{month_data['volatility']:.2f}</td>")
                html_content.append(f"</tr>")
            
            html_content.append("</table>")
            
            # Sector performance
            html_content.append("<h2>Sector Performance</h2>")
            html_content.append("<table>")
            html_content.append("<tr><th>Sector</th><th>Return %</th><th>Weight</th></tr>")
            
            for sector_data in data["sector_performance"]:
                html_content.append(f"<tr>")
                html_content.append(f"<td>{sector_data['sector']}</td>")
                html_content.append(f"<td>{sector_data['return']:.2f}%</td>")
                html_content.append(f"<td>{sector_data['weight']:.2%}</td>")
                html_content.append(f"</tr>")
            
            html_content.append("</table>")
            
            html_content.append("</body></html>")
            
            return "".join(html_content).encode('utf-8')
        
        except Exception as e:
            self.logger.error(f"Error exporting performance to HTML: {e}")
            raise


# Global instance
export_manager = ExportManager()


def get_export_manager() -> ExportManager:
    """Get export manager instance."""
    return export_manager


# API Routes
@exports_bp.route('/portfolio', methods=['POST'])
def export_portfolio():
    """Export portfolio data."""
    try:
        data = request.get_json()
        
        export_type = ExportType.PORTFOLIO_DATA
        format_type = ExportFormat(data.get('format', 'csv'))
        date_range = data.get('date_range', {})
        symbols = data.get('symbols')
        include_charts = data.get('include_charts', True)
        include_summary = data.get('include_summary', True)
        
        config = ExportConfig(
            export_type=export_type,
            format=format_type,
            date_range=date_range,
            symbols=symbols,
            include_charts=include_charts,
            include_summary=include_summary
        )
        
        exported_data = export_manager.export_portfolio_data(config)
        
        # Set appropriate headers for file download
        filename = f"portfolio_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{format_type.value}"
        
        return send_file(
            io.BytesIO(exported_data),
            as_attachment=True,
            download_name=filename,
            mimetype='application/octet-stream'
        )
        
    except Exception as e:
        logger.error(f"Error exporting portfolio: {e}")
        return jsonify({"error": str(e)}), 500


@exports_bp.route('/transactions', methods=['POST'])
def export_transactions():
    """Export transactions data."""
    try:
        data = request.get_json()
        
        export_type = ExportType.TRANSACTIONS
        format_type = ExportFormat(data.get('format', 'csv'))
        date_range = data.get('date_range', {})
        
        config = ExportConfig(
            export_type=export_type,
            format=format_type,
            date_range=date_range
        )
        
        exported_data = export_manager.export_transactions(config)
        
        filename = f"transactions_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{format_type.value}"
        
        return send_file(
            io.BytesIO(exported_data),
            as_attachment=True,
            download_name=filename,
            mimetype='application/octet-stream'
        )
        
    except Exception as e:
        logger.error(f"Error exporting transactions: {e}")
        return jsonify({"error": str(e)}), 500


@exports_bp.route('/performance', methods=['POST'])
def export_performance():
    """Export performance report."""
    try:
        data = request.get_json()
        
        export_type = ExportType.PERFORMANCE_REPORT
        format_type = ExportFormat(data.get('format', 'pdf'))
        date_range = data.get('date_range', {})
        symbols = data.get('symbols')
        
        config = ExportConfig(
            export_type=export_type,
            format=format_type,
            date_range=date_range,
            symbols=symbols
        )
        
        exported_data = export_manager.export_performance_report(config)
        
        filename = f"performance_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{format_type.value}"
        
        return send_file(
            io.BytesIO(exported_data),
            as_attachment=True,
            download_name=filename,
            mimetype='application/octet-stream'
        )
        
    except Exception as e:
        logger.error(f"Error exporting performance: {e}")
        return jsonify({"error": str(e)}), 500


@exports_bp.route('/risk', methods=['POST'])
def export_risk():
    """Export risk analysis."""
    try:
        data = request.get_json()
        
        export_type = ExportType.RISK_ANALYSIS
        format_type = ExportFormat(data.get('format', 'pdf'))
        
        config = ExportConfig(
            export_type=export_type,
            format=format_type,
            date_range=data.get('date_range', {})
        )
        
        exported_data = export_manager.export_risk_analysis(config)
        
        filename = f"risk_analysis_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{format_type.value}"
        
        return send_file(
            io.BytesIO(exported_data),
            as_attachment=True,
            download_name=filename,
            mimetype='application/octet-stream'
        )
        
    except Exception as e:
        logger.error(f"Error exporting risk: {e}")
        return jsonify({"error": str(e)}), 500


@exports_bp.route('/market', methods=['POST'])
def export_market():
    """Export market data."""
    try:
        data = request.get_json()
        
        export_type = ExportType.MARKET_DATA
        format_type = ExportFormat(data.get('format', 'csv'))
        date_range = data.get('date_range', {})
        symbols = data.get('symbols', [])
        
        config = ExportConfig(
            export_type=export_type,
            format=format_type,
            date_range=date_range,
            symbols=symbols
        )
        
        exported_data = export_manager.export_market_data(config)
        
        filename = f"market_data_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{format_type.value}"
        
        return send_file(
            io.BytesIO(exported_data),
            as_attachment=True,
            download_name=filename,
            mimetype='application/octet-stream'
        )
        
    except Exception as e:
        logger.error(f"Error exporting market data: {e}")
        return jsonify({"error": str(e)}), 500


@exports_bp.route('/formats', methods=['GET'])
def get_export_formats():
    """Get available export formats."""
    try:
        return jsonify({
            "formats": [format_type.value for format_type in ExportFormat],
            "types": [export_type.value for export_type in ExportType]
        })
        
    except Exception as e:
        logger.error(f"Error getting export formats: {e}")
        return jsonify({"error": str(e)}), 500
