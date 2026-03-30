"""
Advanced risk management for stop-loss, take-profit, and portfolio analysis.
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache
from app.infrastructure.metrics import get_metrics

logger = logging.getLogger(__name__)


class OrderType(Enum):
    """Order types for risk management."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"


class RiskLevel(Enum):
    """Risk levels for positions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class StopLossConfig:
    """Stop-loss configuration."""
    method: str  # "percentage", "atr", "support", "volatility"
    value: float
    trailing: bool = False
    trailing_amount: float = 0.0
    max_loss_percent: float = 0.05  # Maximum 5% loss
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TakeProfitConfig:
    """Take-profit configuration."""
    method: str  # "percentage", "resistance", "target", "risk_reward"
    value: float
    partial_levels: List[float] = None  # Partial take-profit levels
    auto_adjust: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if self.partial_levels is None:
            result["partial_levels"] = []
        return result


@dataclass
class PositionRisk:
    """Risk analysis for a single position."""
    symbol: str
    entry_price: float
    current_price: float
    quantity: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    stop_loss_price: Optional[float]
    take_profit_price: Optional[float]
    risk_amount: float
    reward_amount: float
    risk_reward_ratio: float
    days_held: int
    max_drawdown: float
    current_drawdown: float
    volatility: float
    beta: float
    var_95: float
    sharpe_ratio: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PortfolioRisk:
    """Risk analysis for entire portfolio."""
    total_value: float
    total_pnl: float
    total_pnl_percent: float
    positions: List[PositionRisk]
    diversification_score: float
    concentration_risk: float
    correlation_risk: float
    portfolio_var: float
    portfolio_beta: float
    max_drawdown: float
    current_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    var_95: float
    expected_shortfall: float
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["positions"] = [pos.to_dict() for pos in self.positions]
        return result


class RiskManager(LoggerMixin):
    """Advanced risk management system."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.risk_free_rate = 0.02  # 2% annual risk-free rate
        self.trading_days_per_year = 252
    
    def calculate_stop_loss(self, entry_price: float, current_price: float, 
                          volatility: float, atr: float = None, 
                          support_levels: List[float] = None,
                          config: StopLossConfig = None) -> float:
        """Calculate optimal stop-loss price."""
        try:
            if config is None:
                # Default configuration
                config = StopLossConfig(method="percentage", value=0.02)
            
            if config.method == "percentage":
                # Percentage-based stop-loss
                stop_loss = entry_price * (1 - config.value)
            
            elif config.method == "atr":
                # ATR-based stop-loss
                if atr is None:
                    # Estimate ATR from volatility
                    atr = entry_price * volatility * np.sqrt(252) * 0.02  # Rough estimate
                
                multiplier = config.value  # Usually 2x ATR
                stop_loss = current_price - (atr * multiplier)
            
            elif config.method == "support":
                # Support level-based stop-loss
                if support_levels is None or not support_levels:
                    # Fallback to percentage
                    stop_loss = entry_price * (1 - config.value)
                else:
                    # Use nearest support level below current price
                    valid_supports = [s for s in support_levels if s < current_price]
                    if valid_supports:
                        stop_loss = max(valid_supports)
                    else:
                        stop_loss = entry_price * (1 - config.value)
            
            elif config.method == "volatility":
                # Volatility-based stop-loss
                # Use 2x daily volatility as stop-loss distance
                daily_vol = volatility / np.sqrt(252)
                stop_loss = current_price * (1 - config.value * daily_vol)
            
            else:
                # Default to percentage
                stop_loss = entry_price * (1 - config.value)
            
            # Ensure stop-loss is not too far from entry price
            max_loss_price = entry_price * (1 - config.max_loss_percent)
            stop_loss = max(stop_loss, max_loss_price)
            
            # Ensure stop-loss is below current price
            stop_loss = min(stop_loss, current_price * 0.999)
            
            return stop_loss
            
        except Exception as e:
            self.logger.error(f"Error calculating stop-loss: {e}")
            return entry_price * 0.95  # Conservative fallback
    
    def calculate_take_profit(self, entry_price: float, current_price: float,
                           volatility: float, resistance_levels: List[float] = None,
                           risk_amount: float = None,
                           config: TakeProfitConfig = None) -> float:
        """Calculate optimal take-profit price."""
        try:
            if config is None:
                # Default configuration
                config = TakeProfitConfig(method="percentage", value=0.03)
            
            if config.method == "percentage":
                # Percentage-based take-profit
                take_profit = entry_price * (1 + config.value)
            
            elif config.method == "resistance":
                # Resistance level-based take-profit
                if resistance_levels is None or not resistance_levels:
                    # Fallback to percentage
                    take_profit = entry_price * (1 + config.value)
                else:
                    # Use nearest resistance level above current price
                    valid_resistances = [r for r in resistance_levels if r > current_price]
                    if valid_resistances:
                        take_profit = min(valid_resistances)
                    else:
                        take_profit = entry_price * (1 + config.value)
            
            elif config.method == "target":
                # Target price-based (would come from prediction model)
                # For now, fallback to percentage
                take_profit = entry_price * (1 + config.value)
            
            elif config.method == "risk_reward":
                # Risk/reward ratio-based (typically 1:2 or 1:3)
                if risk_amount is None:
                    # Estimate risk from volatility
                    risk_amount = entry_price * volatility * 2
                
                target_ratio = config.value  # Usually 2 or 3
                take_profit = entry_price + (risk_amount * target_ratio)
            
            else:
                # Default to percentage
                take_profit = entry_price * (1 + config.value)
            
            # Ensure take-profit is above current price
            take_profit = max(take_profit, current_price * 1.001)
            
            return take_profit
            
        except Exception as e:
            self.logger.error(f"Error calculating take-profit: {e}")
            return entry_price * 1.05  # Conservative fallback
    
    def calculate_position_risk(self, symbol: str, entry_price: float, current_price: float,
                           quantity: float, stop_loss: float = None, take_profit: float = None,
                           historical_data: pd.DataFrame = None) -> PositionRisk:
        """Calculate comprehensive risk analysis for a position."""
        try:
            # Calculate basic metrics
            unrealized_pnl = (current_price - entry_price) * quantity
            unrealized_pnl_percent = (current_price / entry_price - 1) * 100
            
            # Calculate risk and reward amounts
            if stop_loss:
                risk_amount = (entry_price - stop_loss) * quantity
            else:
                # Estimate risk from volatility
                if historical_data is not None and not historical_data.empty:
                    volatility = historical_data['close'].pct_change().std()
                    risk_amount = entry_price * volatility * 2 * quantity
                else:
                    risk_amount = entry_price * 0.05 * quantity  # 5% default risk
            
            if take_profit:
                reward_amount = (take_profit - entry_price) * quantity
            else:
                # Estimate reward (typically 2x risk)
                reward_amount = risk_amount * 2
            
            risk_reward_ratio = reward_amount / abs(risk_amount) if risk_amount != 0 else 0
            
            # Calculate drawdown
            if historical_data is not None and not historical_data.empty:
                # Calculate max drawdown from historical data
                cumulative_returns = (historical_data['close'] / entry_price - 1) * quantity
                running_max = cumulative_returns.expanding().max()
                drawdown = (cumulative_returns - running_max) / running_max
                max_drawdown = drawdown.min()
                
                # Current drawdown
                current_return = (current_price / entry_price - 1)
                current_drawdown = 0  # Would need more data for current drawdown
                
                # Volatility
                volatility = historical_data['close'].pct_change().std()
                
                # Beta (assuming market beta calculation)
                market_returns = historical_data['close'].pct_change()
                beta = 1.0  # Simplified - would calculate against market index
                
                # VaR
                var_95 = np.percentile(historical_data['close'].pct_change(), 5) * quantity
                
                # Sharpe ratio
                excess_returns = historical_data['close'].pct_change() - (self.risk_free_rate / 252)
                sharpe_ratio = excess_returns.mean() / excess_returns.std() * np.sqrt(252) if excess_returns.std() > 0 else 0
            else:
                # Default values if no historical data
                max_drawdown = 0
                current_drawdown = 0
                volatility = 0.2  # 20% annual volatility
                beta = 1.0
                var_95 = -0.05 * quantity  # 5% daily VaR
                sharpe_ratio = 0.5
            
            # Days held (simplified)
            days_held = 1  # Would calculate from entry date
            
            return PositionRisk(
                symbol=symbol,
                entry_price=entry_price,
                current_price=current_price,
                quantity=quantity,
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_percent=unrealized_pnl_percent,
                stop_loss_price=stop_loss,
                take_profit_price=take_profit,
                risk_amount=abs(risk_amount),
                reward_amount=reward_amount,
                risk_reward_ratio=risk_reward_ratio,
                days_held=days_held,
                max_drawdown=max_drawdown,
                current_drawdown=current_drawdown,
                volatility=volatility,
                beta=beta,
                var_95=var_95,
                sharpe_ratio=sharpe_ratio
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating position risk: {e}")
            raise
    
    def calculate_portfolio_risk(self, positions: List[PositionRisk], 
                              correlation_matrix: pd.DataFrame = None) -> PortfolioRisk:
        """Calculate comprehensive portfolio risk analysis."""
        try:
            if not positions:
                raise ValueError("No positions provided")
            
            # Calculate total portfolio metrics
            total_value = sum(abs(pos.current_price * pos.quantity) for pos in positions)
            total_pnl = sum(pos.unrealized_pnl for pos in positions)
            total_pnl_percent = (total_pnl / total_value) * 100 if total_value > 0 else 0
            
            # Calculate diversification score
            diversification_score = self._calculate_diversification_score(positions)
            
            # Calculate concentration risk
            concentration_risk = self._calculate_concentration_risk(positions)
            
            # Calculate correlation risk
            correlation_risk = self._calculate_correlation_risk(correlation_matrix) if correlation_matrix is not None else 0
            
            # Calculate portfolio-level metrics
            portfolio_var = self._calculate_portfolio_var(positions, correlation_matrix)
            portfolio_beta = self._calculate_portfolio_beta(positions)
            
            # Calculate portfolio drawdown
            portfolio_returns = self._calculate_portfolio_returns(positions)
            max_drawdown = self._calculate_max_drawdown(portfolio_returns)
            current_drawdown = self._calculate_current_drawdown(portfolio_returns)
            
            # Calculate portfolio performance ratios
            excess_returns = portfolio_returns - (self.risk_free_rate / 252)
            sharpe_ratio = excess_returns.mean() / excess_returns.std() * np.sqrt(252) if excess_returns.std() > 0 else 0
            
            # Sortino ratio (downside deviation)
            downside_returns = portfolio_returns[portfolio_returns < 0]
            sortino_ratio = portfolio_returns.mean() / downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 and downside_returns.std() > 0 else 0
            
            # Calmar ratio
            calmar_ratio = portfolio_returns.mean() * 252 / abs(max_drawdown) if max_drawdown != 0 else 0
            
            # Portfolio VaR
            portfolio_var_95 = np.percentile(portfolio_returns, 5)
            
            # Expected Shortfall
            var_95 = np.percentile(portfolio_returns, 5)
            expected_shortfall = portfolio_returns[portfolio_returns <= var_95].mean()
            
            return PortfolioRisk(
                total_value=total_value,
                total_pnl=total_pnl,
                total_pnl_percent=total_pnl_percent,
                positions=positions,
                diversification_score=diversification_score,
                concentration_risk=concentration_risk,
                correlation_risk=correlation_risk,
                portfolio_var=portfolio_var,
                portfolio_beta=portfolio_beta,
                max_drawdown=max_drawdown,
                current_drawdown=current_drawdown,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                calmar_ratio=calmar_ratio,
                var_95=portfolio_var_95,
                expected_shortfall=expected_shortfall
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating portfolio risk: {e}")
            raise
    
    def _calculate_diversification_score(self, positions: List[PositionRisk]) -> float:
        """Calculate portfolio diversification score (0-1)."""
        try:
            if len(positions) <= 1:
                return 0.0
            
            # Calculate weight distribution
            total_value = sum(abs(pos.current_price * pos.quantity) for pos in positions)
            weights = [abs(pos.current_price * pos.quantity) / total_value for pos in positions]
            
            # Herfindahl-Hirschman Index
            hhi = sum(w**2 for w in weights)
            
            # Convert to diversification score (inverse of HHI)
            max_hhi = 1.0  # When all weight is in one position
            min_hhi = 1.0 / len(positions)  # When weights are equally distributed
            
            if hhi <= min_hhi:
                return 1.0
            elif hhi >= max_hhi:
                return 0.0
            else:
                # Linear scaling
                return (max_hhi - hhi) / (max_hhi - min_hhi)
            
        except Exception as e:
            self.logger.error(f"Error calculating diversification score: {e}")
            return 0.0
    
    def _calculate_concentration_risk(self, positions: List[PositionRisk]) -> float:
        """Calculate concentration risk (0-1)."""
        try:
            if len(positions) <= 1:
                return 1.0
            
            # Calculate weight distribution
            total_value = sum(abs(pos.current_price * pos.quantity) for pos in positions)
            weights = [abs(pos.current_price * pos.quantity) / total_value for pos in positions]
            
            # Gini coefficient
            sorted_weights = sorted(weights)
            n = len(sorted_weights)
            cumsum_weights = np.cumsum(sorted_weights)
            
            gini = (n + 1 - 2 * np.sum(cumsum_weights)) / (n * np.sum(sorted_weights)) if np.sum(sorted_weights) > 0 else 0
            
            return abs(gini)
            
        except Exception as e:
            self.logger.error(f"Error calculating concentration risk: {e}")
            return 0.0
    
    def _calculate_correlation_risk(self, correlation_matrix: pd.DataFrame) -> float:
        """Calculate correlation risk (0-1)."""
        try:
            if correlation_matrix is None or correlation_matrix.empty:
                return 0.0
            
            # Calculate average off-diagonal correlation
            n = correlation_matrix.shape[0]
            if n <= 1:
                return 0.0
            
            # Get upper triangle (excluding diagonal)
            upper_triangle = correlation_matrix.values[np.triu_indices(n, k=1)]
            
            # Average absolute correlation
            avg_correlation = np.mean(np.abs(upper_triangle))
            
            return avg_correlation
            
        except Exception as e:
            self.logger.error(f"Error calculating correlation risk: {e}")
            return 0.0
    
    def _calculate_portfolio_var(self, positions: List[PositionRisk], correlation_matrix: pd.DataFrame = None) -> float:
        """Calculate portfolio VaR."""
        try:
            if correlation_matrix is None:
                # Simplified calculation without correlation
                total_var = sum(pos.var_95 ** 2 for pos in positions)
                return np.sqrt(total_var)
            
            # Calculate portfolio VaR with correlation
            var_vector = np.array([pos.var_95 for pos in positions])
            correlation_mat = correlation_matrix.values
            
            portfolio_variance = var_vector @ correlation_mat @ var_vector
            return np.sqrt(portfolio_variance)
            
        except Exception as e:
            self.logger.error(f"Error calculating portfolio VaR: {e}")
            return 0.0
    
    def _calculate_portfolio_beta(self, positions: List[PositionRisk]) -> float:
        """Calculate portfolio beta."""
        try:
            if not positions:
                return 1.0
            
            # Weighted average beta
            total_value = sum(abs(pos.current_price * pos.quantity) for pos in positions)
            weighted_beta = sum(pos.beta * abs(pos.current_price * pos.quantity) for pos in positions)
            
            return weighted_beta / total_value if total_value > 0 else 1.0
            
        except Exception as e:
            self.logger.error(f"Error calculating portfolio beta: {e}")
            return 1.0
    
    def _calculate_portfolio_returns(self, positions: List[PositionRisk]) -> np.ndarray:
        """Calculate portfolio returns (simplified)."""
        try:
            if not positions:
                return np.array([])
            
            # Simplified: use average of position returns
            returns = []
            for pos in positions:
                # Create simple return series for each position
                position_return = pos.unrealized_pnl_percent / 100
                returns.append(position_return)
            
            return np.array(returns)
            
        except Exception as e:
            self.logger.error(f"Error calculating portfolio returns: {e}")
            return np.array([])
    
    def _calculate_max_drawdown(self, returns: np.ndarray) -> float:
        """Calculate maximum drawdown."""
        try:
            if len(returns) == 0:
                return 0.0
            
            cumulative = np.cumprod(1 + returns)
            running_max = np.maximum.accumulate(cumulative)
            drawdown = (cumulative - running_max) / running_max
            
            return np.min(drawdown)
            
        except Exception as e:
            self.logger.error(f"Error calculating max drawdown: {e}")
            return 0.0
    
    def _calculate_current_drawdown(self, returns: np.ndarray) -> float:
        """Calculate current drawdown."""
        try:
            if len(returns) == 0:
                return 0.0
            
            cumulative = np.cumprod(1 + returns)
            running_max = np.maximum.accumulate(cumulative)
            drawdown = (cumulative - running_max) / running_max
            
            return drawdown[-1] if len(drawdown) > 0 else 0.0
            
        except Exception as e:
            self.logger.error(f"Error calculating current drawdown: {e}")
            return 0.0
    
    def generate_risk_report(self, portfolio_risk: PortfolioRisk) -> Dict[str, Any]:
        """Generate comprehensive risk report."""
        try:
            # Risk assessment
            risk_level = self._assess_risk_level(portfolio_risk)
            
            # Recommendations
            recommendations = self._generate_risk_recommendations(portfolio_risk)
            
            # Visualizations
            visualizations = self._create_risk_visualizations(portfolio_risk)
            
            return {
                "portfolio_risk": portfolio_risk.to_dict(),
                "risk_assessment": {
                    "risk_level": risk_level,
                    "risk_score": self._calculate_risk_score(portfolio_risk),
                    "key_metrics": {
                        "diversification_score": portfolio_risk.diversification_score,
                        "concentration_risk": portfolio_risk.concentration_risk,
                        "correlation_risk": portfolio_risk.correlation_risk,
                        "max_drawdown": portfolio_risk.max_drawdown,
                        "sharpe_ratio": portfolio_risk.sharpe_ratio,
                        "portfolio_var": portfolio_risk.portfolio_var
                    }
                },
                "recommendations": recommendations,
                "visualizations": visualizations,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error generating risk report: {e}")
            return {}
    
    def _assess_risk_level(self, portfolio_risk: PortfolioRisk) -> str:
        """Assess overall risk level."""
        try:
            risk_score = 0
            
            # Drawdown risk
            if abs(portfolio_risk.max_drawdown) > 0.2:
                risk_score += 3
            elif abs(portfolio_risk.max_drawdown) > 0.1:
                risk_score += 2
            elif abs(portfolio_risk.max_drawdown) > 0.05:
                risk_score += 1
            
            # Concentration risk
            if portfolio_risk.concentration_risk > 0.7:
                risk_score += 3
            elif portfolio_risk.concentration_risk > 0.5:
                risk_score += 2
            elif portfolio_risk.concentration_risk > 0.3:
                risk_score += 1
            
            # Correlation risk
            if portfolio_risk.correlation_risk > 0.8:
                risk_score += 2
            elif portfolio_risk.correlation_risk > 0.6:
                risk_score += 1
            
            # Performance risk
            if portfolio_risk.sharpe_ratio < 0:
                risk_score += 2
            elif portfolio_risk.sharpe_ratio < 0.5:
                risk_score += 1
            
            # Determine risk level
            if risk_score >= 7:
                return "EXTREME"
            elif risk_score >= 5:
                return "HIGH"
            elif risk_score >= 3:
                return "MEDIUM"
            else:
                return "LOW"
            
        except Exception as e:
            self.logger.error(f"Error assessing risk level: {e}")
            return "UNKNOWN"
    
    def _calculate_risk_score(self, portfolio_risk: PortfolioRisk) -> float:
        """Calculate overall risk score (0-100)."""
        try:
            score = 50  # Base score
            
            # Adjust for drawdown
            score -= abs(portfolio_risk.max_drawdown) * 100
            
            # Adjust for diversification
            score += portfolio_risk.diversification_score * 20
            
            # Adjust for Sharpe ratio
            score += portfolio_risk.sharpe_ratio * 10
            
            # Adjust for concentration risk (negative impact)
            score -= portfolio_risk.concentration_risk * 30
            
            # Adjust for correlation risk (negative impact)
            score -= portfolio_risk.correlation_risk * 20
            
            return max(0, min(100, score))
            
        except Exception as e:
            self.logger.error(f"Error calculating risk score: {e}")
            return 50.0
    
    def _generate_risk_recommendations(self, portfolio_risk: PortfolioRisk) -> List[str]:
        """Generate risk management recommendations."""
        try:
            recommendations = []
            
            # Diversification recommendations
            if portfolio_risk.diversification_score < 0.5:
                recommendations.append("Consider diversifying portfolio to reduce concentration risk")
            
            # Concentration risk
            if portfolio_risk.concentration_risk > 0.6:
                recommendations.append("Reduce position sizes to lower concentration risk")
            
            # Correlation risk
            if portfolio_risk.correlation_risk > 0.7:
                recommendations.append("Add uncorrelated assets to reduce portfolio correlation")
            
            # Drawdown risk
            if abs(portfolio_risk.max_drawdown) > 0.15:
                recommendations.append("Implement stricter stop-loss policies to limit drawdowns")
            
            # Performance recommendations
            if portfolio_risk.sharpe_ratio < 0.5:
                recommendations.append("Review portfolio composition to improve risk-adjusted returns")
            
            # VaR recommendations
            if portfolio_risk.portfolio_var > 0.05:
                recommendations.append("Consider reducing position sizes to lower portfolio VaR")
            
            return recommendations
            
        except Exception as e:
            self.logger.error(f"Error generating recommendations: {e}")
            return []
    
    def _create_risk_visualizations(self, portfolio_risk: PortfolioRisk) -> Dict[str, str]:
        """Create risk visualization charts."""
        try:
            visualizations = {}
            
            # Position risk chart
            if portfolio_risk.positions:
                symbols = [pos.symbol for pos in portfolio_risk.positions]
                pnl_percentages = [pos.unrealized_pnl_percent for pos in portfolio_risk.positions]
                risk_ratios = [pos.risk_reward_ratio for pos in portfolio_risk.positions]
                
                # PnL chart
                fig1 = go.Figure()
                fig1.add_trace(go.Bar(
                    x=symbols,
                    y=pnl_percentages,
                    name="PnL %",
                    marker_color=['green' if pnl > 0 else 'red' for pnl in pnl_percentages]
                ))
                fig1.update_layout(
                    title="Position P&L Performance",
                    xaxis_title="Symbol",
                    yaxis_title="P&L (%)"
                )
                visualizations["pnl_chart"] = fig1.to_html(include_plotlyjs='cdn')
                
                # Risk/Reward chart
                fig2 = go.Figure()
                fig2.add_trace(go.Bar(
                    x=symbols,
                    y=risk_ratios,
                    name="Risk/Reward Ratio"
                ))
                fig2.update_layout(
                    title="Risk/Reward Ratios",
                    xaxis_title="Symbol",
                    yaxis_title="Risk/Reward Ratio"
                )
                visualizations["risk_reward_chart"] = fig2.to_html(include_plotlyjs='cdn')
            
            # Portfolio composition pie chart
            symbols = [pos.symbol for pos in portfolio_risk.positions]
            values = [abs(pos.current_price * pos.quantity) for pos in portfolio_risk.positions]
            
            fig3 = go.Figure(data=[go.Pie(
                labels=symbols,
                values=values,
                title="Portfolio Composition"
            )])
            visualizations["composition_chart"] = fig3.to_html(include_plotlyjs='cdn')
            
            return visualizations
            
        except Exception as e:
            self.logger.error(f"Error creating visualizations: {e}")
            return {}


# Global instance
risk_manager = RiskManager()


def get_risk_manager() -> RiskManager:
    """Get risk manager instance."""
    return risk_manager


# Utility functions
def calculate_stop_loss(entry_price: float, current_price: float, volatility: float, 
                      method: str = "percentage", value: float = 0.02) -> float:
    """Calculate stop-loss price."""
    config = StopLossConfig(method=method, value=value)
    return risk_manager.calculate_stop_loss(entry_price, current_price, volatility, config=config)


def calculate_take_profit(entry_price: float, current_price: float, volatility: float,
                        method: str = "percentage", value: float = 0.03) -> float:
    """Calculate take-profit price."""
    config = TakeProfitConfig(method=method, value=value)
    return risk_manager.calculate_take_profit(entry_price, current_price, volatility, config=config)


def assess_portfolio_risk(positions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Assess portfolio risk."""
    try:
        # Convert to PositionRisk objects
        position_risks = []
        for pos_data in positions:
            position_risk = PositionRisk(**pos_data)
            position_risks.append(position_risk)
        
        # Calculate portfolio risk
        portfolio_risk = risk_manager.calculate_portfolio_risk(position_risks)
        
        # Generate report
        return risk_manager.generate_risk_report(portfolio_risk)
        
    except Exception as e:
        logger.error(f"Error assessing portfolio risk: {e}")
        return {}
