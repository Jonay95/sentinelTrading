"""
Advanced risk analytics for portfolio-level risk metrics and position sizing.
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import scipy.stats as stats
from scipy.optimize import minimize
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache
from app.infrastructure.metrics import get_metrics

logger = logging.getLogger(__name__)


class RiskMetric(Enum):
    """Types of risk metrics."""
    VALUE_AT_RISK = "value_at_risk"
    EXPECTED_SHORTFALL = "expected_shortfall"
    MAX_DRAWDOWN = "max_drawdown"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    BETA = "beta"
    ALPHA = "alpha"
    INFORMATION_RATIO = "information_ratio"
    TREYNOR_RATIO = "treynor_ratio"


class PositionSizingMethod(Enum):
    """Position sizing methods."""
    FIXED_FRACTIONAL = "fixed_fractional"
    KELLY_CRITERION = "kelly_criterion"
    VOLATILITY_TARGETING = "volatility_targeting"
    RISK_PARITY = "risk_parity"
    EQUAL_WEIGHT = "equal_weight"
    OPTIMAL_F = "optimal_f"


@dataclass
class PortfolioMetrics:
    """Portfolio risk and performance metrics."""
    total_value: float
    cash: float
    positions: Dict[str, float]  # symbol -> quantity
    weights: Dict[str, float]  # symbol -> weight
    returns: List[float]
    timestamps: List[datetime]
    risk_metrics: Dict[str, float]
    performance_metrics: Dict[str, float]
    correlation_matrix: Dict[str, Dict[str, float]]
    var_breakdown: Dict[str, float]
    concentration_metrics: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['timestamps'] = [ts.isoformat() for ts in self.timestamps]
        return result


@dataclass
class Position:
    """Individual position information."""
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    weight: float
    beta: float
    volatility: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RiskAnalytics(LoggerMixin):
    """Advanced risk analytics for portfolio management."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.risk_free_rate = 0.02  # 2% annual risk-free rate
        self.trading_days_per_year = 252
    
    def calculate_portfolio_metrics(self, positions: Dict[str, float], 
                                  prices: Dict[str, pd.DataFrame],
                                  cash: float = 0.0) -> PortfolioMetrics:
        """Calculate comprehensive portfolio risk metrics."""
        try:
            # Calculate current market values
            current_values = {}
            total_market_value = cash
            
            for symbol, quantity in positions.items():
                if symbol in prices and not prices[symbol].empty:
                    current_price = prices[symbol]['close'].iloc[-1]
                    market_value = quantity * current_price
                    current_values[symbol] = market_value
                    total_market_value += market_value
            
            # Calculate weights
            weights = {}
            for symbol, value in current_values.items():
                weights[symbol] = value / total_market_value if total_market_value > 0 else 0
            
            # Calculate portfolio returns
            portfolio_returns = self._calculate_portfolio_returns(positions, prices, weights)
            
            # Calculate risk metrics
            risk_metrics = self._calculate_risk_metrics(portfolio_returns, weights, prices)
            
            # Calculate performance metrics
            performance_metrics = self._calculate_performance_metrics(portfolio_returns)
            
            # Calculate correlation matrix
            correlation_matrix = self._calculate_correlation_matrix(prices, weights.keys())
            
            # Calculate VaR breakdown
            var_breakdown = self._calculate_var_breakdown(weights, risk_metrics, correlation_matrix)
            
            # Calculate concentration metrics
            concentration_metrics = self._calculate_concentration_metrics(weights)
            
            return PortfolioMetrics(
                total_value=total_market_value,
                cash=cash,
                positions=positions,
                weights=weights,
                returns=portfolio_returns,
                timestamps=[prices[symbol].index[-1] for symbol in prices.keys() if symbol in weights],
                risk_metrics=risk_metrics,
                performance_metrics=performance_metrics,
                correlation_matrix=correlation_matrix,
                var_breakdown=var_breakdown,
                concentration_metrics=concentration_metrics
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating portfolio metrics: {e}")
            raise
    
    def _calculate_portfolio_returns(self, positions: Dict[str, float], 
                                   prices: Dict[str, pd.DataFrame],
                                   weights: Dict[str, float]) -> List[float]:
        """Calculate portfolio time-series returns."""
        try:
            # Get common date range
            start_dates = []
            end_dates = []
            
            for symbol in weights.keys():
                if symbol in prices and not prices[symbol].empty:
                    start_dates.append(prices[symbol].index[0])
                    end_dates.append(prices[symbol].index[-1])
            
            if not start_dates:
                return []
            
            common_start = max(start_dates)
            common_end = min(end_dates)
            
            if common_start >= common_end:
                return []
            
            # Calculate daily returns for each asset
            asset_returns = {}
            
            for symbol, weight in weights.items():
                if symbol in prices and not prices[symbol].empty:
                    price_data = prices[symbol].loc[common_start:common_end]
                    
                    if len(price_data) > 1:
                        returns = price_data['close'].pct_change().dropna()
                        asset_returns[symbol] = returns * weight
            
            # Sum weighted returns to get portfolio returns
            if asset_returns:
                portfolio_df = pd.DataFrame(asset_returns)
                portfolio_returns = portfolio_df.sum(axis=1).fillna(0).tolist()
            else:
                portfolio_returns = []
            
            return portfolio_returns
            
        except Exception as e:
            self.logger.error(f"Error calculating portfolio returns: {e}")
            return []
    
    def _calculate_risk_metrics(self, returns: List[float], weights: Dict[str, float],
                              prices: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        """Calculate risk metrics."""
        try:
            if not returns:
                return {}
            
            returns_array = np.array(returns)
            
            risk_metrics = {}
            
            # Basic volatility
            risk_metrics['volatility'] = np.std(returns_array) * np.sqrt(self.trading_days_per_year)
            
            # Value at Risk (95% and 99%)
            risk_metrics['var_95'] = np.percentile(returns_array, 5) * np.sqrt(self.trading_days_per_year)
            risk_metrics['var_99'] = np.percentile(returns_array, 1) * np.sqrt(self.trading_days_per_year)
            
            # Expected Shortfall (5% and 1%)
            var_95 = np.percentile(returns_array, 5)
            var_99 = np.percentile(returns_array, 1)
            
            risk_metrics['expected_shortfall_95'] = returns_array[returns_array <= var_95].mean() * np.sqrt(self.trading_days_per_year)
            risk_metrics['expected_shortfall_99'] = returns_array[returns_array <= var_99].mean() * np.sqrt(self.trading_days_per_year)
            
            # Maximum Drawdown
            risk_metrics['max_drawdown'] = self._calculate_max_drawdown(returns_array)
            
            # Beta (assuming market return is the equal-weighted average)
            market_returns = self._calculate_market_returns(prices, weights.keys())
            if len(market_returns) == len(returns_array):
                beta = self._calculate_beta(returns_array, market_returns)
                risk_metrics['beta'] = beta
            else:
                risk_metrics['beta'] = 1.0
            
            # Portfolio VaR (weighted sum of individual VaRs)
            portfolio_var = 0
            for symbol, weight in weights.items():
                if symbol in prices and not prices[symbol].empty:
                    price_returns = prices[symbol]['close'].pct_change().dropna()
                    if len(price_returns) > 0:
                        individual_var = np.percentile(price_returns, 5) * np.sqrt(self.trading_days_per_year)
                        portfolio_var += (weight ** 2) * (individual_var ** 2)
            
            risk_metrics['portfolio_var'] = np.sqrt(portfolio_var)
            
            return risk_metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating risk metrics: {e}")
            return {}
    
    def _calculate_performance_metrics(self, returns: List[float]) -> Dict[str, float]:
        """Calculate performance metrics."""
        try:
            if not returns:
                return {}
            
            returns_array = np.array(returns)
            
            performance_metrics = {}
            
            # Total return
            performance_metrics['total_return'] = (1 + returns_array).prod() - 1
            
            # Annualized return
            performance_metrics['annualized_return'] = (1 + np.mean(returns_array)) ** self.trading_days_per_year - 1
            
            # Sharpe ratio
            excess_returns = returns_array - self.risk_free_rate / self.trading_days_per_year
            if np.std(excess_returns) > 0:
                performance_metrics['sharpe_ratio'] = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(self.trading_days_per_year)
            else:
                performance_metrics['sharpe_ratio'] = 0
            
            # Sortino ratio (downside deviation)
            downside_returns = returns_array[returns_array < 0]
            if len(downside_returns) > 0 and np.std(downside_returns) > 0:
                performance_metrics['sortino_ratio'] = np.mean(returns_array) / np.std(downside_returns) * np.sqrt(self.trading_days_per_year)
            else:
                performance_metrics['sortino_ratio'] = 0
            
            # Calmar ratio (return / max drawdown)
            max_dd = self._calculate_max_drawdown(returns_array)
            if max_dd > 0:
                performance_metrics['calmar_ratio'] = performance_metrics['annualized_return'] / max_dd
            else:
                performance_metrics['calmar_ratio'] = 0
            
            # Win rate
            performance_metrics['win_rate'] = (returns_array > 0).mean()
            
            # Profit factor
            winning_returns = returns_array[returns_array > 0]
            losing_returns = returns_array[returns_array < 0]
            
            if len(losing_returns) > 0:
                performance_metrics['profit_factor'] = winning_returns.sum() / abs(losing_returns.sum())
            else:
                performance_metrics['profit_factor'] = float('inf') if len(winning_returns) > 0 else 0
            
            return performance_metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating performance metrics: {e}")
            return {}
    
    def _calculate_correlation_matrix(self, prices: Dict[str, pd.DataFrame], symbols: List[str]) -> Dict[str, Dict[str, float]]:
        """Calculate correlation matrix."""
        try:
            returns_data = {}
            
            for symbol in symbols:
                if symbol in prices and not prices[symbol].empty:
                    returns = prices[symbol]['close'].pct_change().dropna()
                    if len(returns) > 0:
                        returns_data[symbol] = returns
            
            if len(returns_data) < 2:
                return {}
            
            # Create DataFrame and calculate correlation
            returns_df = pd.DataFrame(returns_data)
            correlation_matrix = returns_df.corr()
            
            # Convert to nested dictionary
            corr_dict = {}
            for symbol1 in correlation_matrix.index:
                corr_dict[symbol1] = {}
                for symbol2 in correlation_matrix.columns:
                    corr_dict[symbol1][symbol2] = correlation_matrix.loc[symbol1, symbol2]
            
            return corr_dict
            
        except Exception as e:
            self.logger.error(f"Error calculating correlation matrix: {e}")
            return {}
    
    def _calculate_var_breakdown(self, weights: Dict[str, float], risk_metrics: Dict[str, float],
                                correlation_matrix: Dict[str, Dict[str, float]]) -> Dict[str, float]:
        """Calculate VaR breakdown by asset."""
        try:
            if not weights or not risk_metrics or not correlation_matrix:
                return {}
            
            var_breakdown = {}
            
            for symbol, weight in weights.items():
                if symbol in correlation_matrix:
                    # Simplified VaR contribution (marginal VaR approximation)
                    individual_var = risk_metrics.get('var_95', 0)
                    
                    # Account for correlation with portfolio
                    correlation_sum = sum(correlation_matrix[symbol].get(other_symbol, 0) * other_weight 
                                      for other_symbol, other_weight in weights.items())
                    
                    var_contribution = (weight ** 2) * (individual_var ** 2) * correlation_sum
                    var_breakdown[symbol] = var_contribution
            
            return var_breakdown
            
        except Exception as e:
            self.logger.error(f"Error calculating VaR breakdown: {e}")
            return {}
    
    def _calculate_concentration_metrics(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Calculate concentration metrics."""
        try:
            if not weights:
                return {}
            
            weights_array = np.array(list(weights.values()))
            
            concentration_metrics = {}
            
            # Herfindahl-Hirschman Index (HHI)
            hhi = np.sum(weights_array ** 2)
            concentration_metrics['hhi'] = hhi
            
            # Maximum weight
            concentration_metrics['max_weight'] = np.max(weights_array)
            
            # Number of effective positions
            concentration_metrics['effective_positions'] = 1 / hhi if hhi > 0 else 0
            
            # Gini coefficient
            sorted_weights = np.sort(weights_array)
            n = len(sorted_weights)
            cumsum_weights = np.cumsum(sorted_weights)
            gini = (n + 1 - 2 * np.sum(cumsum_weights)) / (n * np.sum(sorted_weights)) if np.sum(sorted_weights) > 0 else 0
            concentration_metrics['gini_coefficient'] = gini
            
            return concentration_metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating concentration metrics: {e}")
            return {}
    
    def _calculate_max_drawdown(self, returns: np.ndarray) -> float:
        """Calculate maximum drawdown."""
        try:
            if len(returns) == 0:
                return 0
            
            cumulative = np.cumprod(1 + returns)
            running_max = np.maximum.accumulate(cumulative)
            drawdown = (cumulative - running_max) / running_max
            
            return np.min(drawdown)
            
        except Exception as e:
            self.logger.error(f"Error calculating max drawdown: {e}")
            return 0
    
    def _calculate_beta(self, returns: np.ndarray, market_returns: np.ndarray) -> float:
        """Calculate beta against market."""
        try:
            if len(returns) != len(market_returns) or len(returns) < 2:
                return 1.0
            
            covariance = np.cov(returns, market_returns)[0, 1]
            market_variance = np.var(market_returns)
            
            return covariance / market_variance if market_variance > 0 else 1.0
            
        except Exception as e:
            self.logger.error(f"Error calculating beta: {e}")
            return 1.0
    
    def _calculate_market_returns(self, prices: Dict[str, pd.DataFrame], symbols: List[str]) -> np.ndarray:
        """Calculate market returns (equal-weighted index)."""
        try:
            market_returns = []
            
            # Get common date range
            start_dates = []
            end_dates = []
            
            for symbol in symbols:
                if symbol in prices and not prices[symbol].empty:
                    start_dates.append(prices[symbol].index[0])
                    end_dates.append(prices[symbol].index[-1])
            
            if not start_dates:
                return np.array([])
            
            common_start = max(start_dates)
            common_end = min(end_dates)
            
            if common_start >= common_end:
                return np.array([])
            
            # Calculate equal-weighted market returns
            asset_returns = []
            
            for symbol in symbols:
                if symbol in prices and not prices[symbol].empty:
                    price_data = prices[symbol].loc[common_start:common_end]
                    
                    if len(price_data) > 1:
                        returns = price_data['close'].pct_change().dropna()
                        asset_returns.append(returns)
            
            if asset_returns:
                market_df = pd.DataFrame(asset_returns).T
                market_returns = market_df.mean(axis=0).fillna(0).values
            else:
                market_returns = np.array([])
            
            return market_returns
            
        except Exception as e:
            self.logger.error(f"Error calculating market returns: {e}")
            return np.array([])


class PositionSizing(LoggerMixin):
    """Position sizing recommendations for risk management."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.max_position_size = 0.2  # Maximum 20% per position
        self.min_position_size = 0.01  # Minimum 1% per position
    
    def calculate_position_sizes(self, portfolio_value: float, signals: Dict[str, Dict[str, Any]],
                                 method: PositionSizingMethod = PositionSizingMethod.FIXED_FRACTIONAL,
                                 risk_per_trade: float = 0.02) -> Dict[str, Dict[str, Any]]:
        """Calculate position sizes based on signals and risk parameters."""
        try:
            position_sizes = {}
            
            for symbol, signal in signals.items():
                position_info = self._calculate_single_position(
                    symbol, signal, portfolio_value, method, risk_per_trade
                )
                position_sizes[symbol] = position_info
            
            # Normalize to ensure total doesn't exceed 100%
            position_sizes = self._normalize_positions(position_sizes, portfolio_value)
            
            return position_sizes
            
        except Exception as e:
            self.logger.error(f"Error calculating position sizes: {e}")
            return {}
    
    def _calculate_single_position(self, symbol: str, signal: Dict[str, Any], portfolio_value: float,
                                 method: PositionSizingMethod, risk_per_trade: float) -> Dict[str, Any]:
        """Calculate position size for a single asset."""
        try:
            position_info = {
                'symbol': symbol,
                'signal': signal.get('signal', 'HOLD'),
                'confidence': signal.get('confidence', 0.5),
                'volatility': signal.get('volatility', 0.2),
                'expected_return': signal.get('expected_return', 0.1),
                'stop_loss': signal.get('stop_loss', 0.05)
            }
            
            if method == PositionSizingMethod.FIXED_FRACTIONAL:
                position_size = self._fixed_fractional_sizing(portfolio_value, risk_per_trade)
            
            elif method == PositionSizingMethod.KELLY_CRITERION:
                position_size = self._kelly_criterion_sizing(
                    signal.get('expected_return', 0.1), 
                    signal.get('volatility', 0.2) ** 2
                )
            
            elif method == PositionSizingMethod.VOLATILITY_TARGETING:
                position_size = self._volatility_targeting_sizing(
                    portfolio_value, signal.get('volatility', 0.2), risk_per_trade
                )
            
            elif method == PositionSizingMethod.RISK_PARITY:
                position_size = self._risk_parity_sizing(portfolio_value, signal.get('volatility', 0.2))
            
            elif method == PositionSizingMethod.EQUAL_WEIGHT:
                position_size = portfolio_value * 0.1  # 10% equal weight
            
            else:
                position_size = portfolio_value * 0.05  # Default 5%
            
            # Apply constraints
            position_size = max(portfolio_size, portfolio_value * self.min_position_size)
            position_size = min(position_size, portfolio_value * self.max_position_size)
            
            # Adjust for confidence
            confidence_adjustment = signal.get('confidence', 0.5)
            position_size *= confidence_adjustment
            
            # Calculate number of shares
            current_price = signal.get('current_price', 100)
            shares = int(position_size / current_price)
            
            position_info.update({
                'position_value': position_size,
                'shares': shares,
                'weight': position_size / portfolio_value,
                'method': method.value
            })
            
            return position_info
            
        except Exception as e:
            self.logger.error(f"Error calculating single position: {e}")
            return {}
    
    def _fixed_fractional_sizing(self, portfolio_value: float, risk_per_trade: float) -> float:
        """Fixed fractional position sizing."""
        return portfolio_value * risk_per_trade
    
    def _kelly_criterion_sizing(self, expected_return: float, variance: float) -> float:
        """Kelly criterion position sizing."""
        if variance <= 0:
            return 0
        
        kelly_fraction = expected_return / variance
        return max(0, min(kelly_fraction, 0.25))  # Cap at 25% to avoid over-leveraging
    
    def _volatility_targeting_sizing(self, portfolio_value: float, volatility: float, risk_per_trade: float) -> float:
        """Volatility targeting position sizing."""
        if volatility <= 0:
            return portfolio_value * 0.05
        
        target_volatility = risk_per_trade
        position_size = (target_volatility / volatility) * portfolio_value
        return position_size
    
    def _risk_parity_sizing(self, portfolio_value: float, volatility: float) -> float:
        """Risk parity position sizing."""
        if volatility <= 0:
            return portfolio_value * 0.05
        
        # Inverse volatility weighting
        inverse_vol = 1 / volatility
        total_inverse_vol = inverse_vol  # Simplified for single position
        
        return portfolio_value * (inverse_vol / total_inverse_vol)
    
    def _normalize_positions(self, position_sizes: Dict[str, Dict[str, Any]], portfolio_value: float) -> Dict[str, Dict[str, Any]]:
        """Normalize positions to ensure total doesn't exceed portfolio value."""
        try:
            total_value = sum(info['position_value'] for info in position_sizes.values())
            
            if total_value <= portfolio_value:
                return position_sizes
            
            # Scale down proportionally
            scaling_factor = portfolio_value / total_value
            
            for symbol, info in position_sizes.items():
                info['position_value'] *= scaling_factor
                info['shares'] = int(info['position_value'] / info.get('current_price', 100))
                info['weight'] *= scaling_factor
            
            return position_sizes
            
        except Exception as e:
            self.logger.error(f"Error normalizing positions: {e}")
            return position_sizes


class RiskManager(LoggerMixin):
    """Comprehensive risk management system."""
    
    def __init__(self):
        self.risk_analytics = RiskAnalytics()
        self.position_sizing = PositionSizing()
        self.metrics = get_metrics()
        self.cache = get_cache()
    
    def assess_portfolio_risk(self, positions: Dict[str, float], prices: Dict[str, pd.DataFrame],
                           cash: float = 0.0) -> Dict[str, Any]:
        """Comprehensive portfolio risk assessment."""
        try:
            # Calculate portfolio metrics
            portfolio_metrics = self.risk_analytics.calculate_portfolio_metrics(positions, prices, cash)
            
            # Risk assessment
            risk_assessment = {
                "overall_risk_level": self._assess_overall_risk(portfolio_metrics),
                "risk_factors": self._identify_risk_factors(portfolio_metrics),
                "recommendations": self._generate_risk_recommendations(portfolio_metrics),
                "alerts": self._generate_risk_alerts(portfolio_metrics)
            }
            
            return {
                "portfolio_metrics": portfolio_metrics.to_dict(),
                "risk_assessment": risk_assessment,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error assessing portfolio risk: {e}")
            return {}
    
    def _assess_overall_risk(self, metrics: PortfolioMetrics) -> str:
        """Assess overall risk level."""
        try:
            risk_score = 0
            
            # Volatility risk
            volatility = metrics.risk_metrics.get('volatility', 0)
            if volatility > 0.3:
                risk_score += 3
            elif volatility > 0.2:
                risk_score += 2
            elif volatility > 0.1:
                risk_score += 1
            
            # Drawdown risk
            max_dd = abs(metrics.risk_metrics.get('max_drawdown', 0))
            if max_dd > 0.2:
                risk_score += 3
            elif max_dd > 0.1:
                risk_score += 2
            elif max_dd > 0.05:
                risk_score += 1
            
            # Concentration risk
            hhi = metrics.concentration_metrics.get('hhi', 0)
            if hhi > 0.5:
                risk_score += 3
            elif hhi > 0.3:
                risk_score += 2
            elif hhi > 0.15:
                risk_score += 1
            
            # VaR risk
            var_95 = abs(metrics.risk_metrics.get('var_95', 0))
            if var_95 > 0.05:
                risk_score += 3
            elif var_95 > 0.03:
                risk_score += 2
            elif var_95 > 0.02:
                risk_score += 1
            
            # Determine risk level
            if risk_score >= 10:
                return "very_high"
            elif risk_score >= 7:
                return "high"
            elif risk_score >= 4:
                return "medium"
            else:
                return "low"
            
        except Exception as e:
            self.logger.error(f"Error assessing overall risk: {e}")
            return "unknown"
    
    def _identify_risk_factors(self, metrics: PortfolioMetrics) -> List[str]:
        """Identify specific risk factors."""
        try:
            risk_factors = []
            
            # High concentration
            max_weight = metrics.concentration_metrics.get('max_weight', 0)
            if max_weight > 0.3:
                risk_factors.append(f"High concentration in single position ({max_weight:.1%})")
            
            # High volatility
            volatility = metrics.risk_metrics.get('volatility', 0)
            if volatility > 0.25:
                risk_factors.append(f"High portfolio volatility ({volatility:.1%})")
            
            # Large drawdown
            max_dd = abs(metrics.risk_metrics.get('max_drawdown', 0))
            if max_dd > 0.15:
                risk_factors.append(f"Significant drawdown ({max_dd:.1%})")
            
            # High VaR
            var_95 = abs(metrics.risk_metrics.get('var_95', 0))
            if var_95 > 0.04:
                risk_factors.append(f"High Value at Risk ({var_95:.1%})")
            
            # Poor diversification
            effective_positions = metrics.concentration_metrics.get('effective_positions', 0)
            if effective_positions < 5:
                risk_factors.append(f"Poor diversification ({effective_positions:.1f} effective positions)")
            
            # High correlation
            avg_correlation = self._calculate_average_correlation(metrics.correlation_matrix)
            if avg_correlation > 0.7:
                risk_factors.append(f"High average correlation ({avg_correlation:.2f})")
            
            return risk_factors
            
        except Exception as e:
            self.logger.error(f"Error identifying risk factors: {e}")
            return []
    
    def _generate_risk_recommendations(self, metrics: PortfolioMetrics) -> List[str]:
        """Generate risk management recommendations."""
        try:
            recommendations = []
            
            # Concentration recommendations
            max_weight = metrics.concentration_metrics.get('max_weight', 0)
            if max_weight > 0.2:
                recommendations.append(f"Consider reducing position size to below 20% (currently {max_weight:.1%})")
            
            # Diversification recommendations
            effective_positions = metrics.concentration_metrics.get('effective_positions', 0)
            if effective_positions < 10:
                recommendations.append(f"Consider diversifying to {max(effective_positions + 5, 15)} positions")
            
            # Volatility recommendations
            volatility = metrics.risk_metrics.get('volatility', 0)
            if volatility > 0.2:
                recommendations.append(f"Consider reducing portfolio volatility (currently {volatility:.1%})")
            
            # Drawdown recommendations
            max_dd = abs(metrics.risk_metrics.get('max_drawdown', 0))
            if max_dd > 0.1:
                recommendations.append("Consider implementing stop-loss strategies to limit drawdowns")
            
            # Rebalancing recommendations
            if metrics.weights:
                # Check if weights are significantly different from equal weight
                equal_weight = 1.0 / len(metrics.weights)
                weight_deviations = [abs(weight - equal_weight) for weight in metrics.weights.values()]
                avg_deviation = np.mean(weight_deviations)
                
                if avg_deviation > 0.1:
                    recommendations.append("Consider portfolio rebalancing to maintain target allocations")
            
            return recommendations
            
        except Exception as e:
            self.logger.error(f"Error generating recommendations: {e}")
            return []
    
    def _generate_risk_alerts(self, metrics: PortfolioMetrics) -> List[Dict[str, Any]]:
        """Generate risk alerts for critical issues."""
        try:
            alerts = []
            
            # Critical concentration alert
            max_weight = metrics.concentration_metrics.get('max_weight', 0)
            if max_weight > 0.4:
                alerts.append({
                    "level": "critical",
                    "type": "concentration",
                    "message": f"Critical concentration detected: {max_weight:.1%} in single position",
                    "threshold": 0.4,
                    "current_value": max_weight
                })
            
            # Critical drawdown alert
            max_dd = abs(metrics.risk_metrics.get('max_drawdown', 0))
            if max_dd > 0.2:
                alerts.append({
                    "level": "critical",
                    "type": "drawdown",
                    "message": f"Critical drawdown detected: {max_dd:.1%}",
                    "threshold": 0.2,
                    "current_value": max_dd
                })
            
            # High VaR alert
            var_95 = abs(metrics.risk_metrics.get('var_95', 0))
            if var_95 > 0.05:
                alerts.append({
                    "level": "high",
                    "type": "var",
                    "message": f"High Value at Risk: {var_95:.1%}",
                    "threshold": 0.05,
                    "current_value": var_95
                })
            
            return alerts
            
        except Exception as e:
            self.logger.error(f"Error generating alerts: {e}")
            return []
    
    def _calculate_average_correlation(self, correlation_matrix: Dict[str, Dict[str, float]]) -> float:
        """Calculate average correlation coefficient."""
        try:
            if not correlation_matrix:
                return 0
            
            correlations = []
            
            for symbol1, correlations_dict in correlation_matrix.items():
                for symbol2, correlation in correlations_dict.items():
                    if symbol1 != symbol2:  # Avoid diagonal elements
                        correlations.append(abs(correlation))
            
            return np.mean(correlations) if correlations else 0
            
        except Exception as e:
            self.logger.error(f"Error calculating average correlation: {e}")
            return 0


# Global instances
risk_analytics = RiskAnalytics()
position_sizing = PositionSizing()
risk_manager = RiskManager()


def get_risk_analytics() -> RiskAnalytics:
    """Get risk analytics instance."""
    return risk_analytics


def get_position_sizing() -> PositionSizing:
    """Get position sizing instance."""
    return position_sizing


def get_risk_manager() -> RiskManager:
    """Get risk manager instance."""
    return risk_manager


# Utility functions
def assess_portfolio_risk(positions: Dict[str, float], prices: Dict[str, pd.DataFrame], cash: float = 0.0) -> Dict[str, Any]:
    """Assess portfolio risk comprehensively."""
    return risk_manager.assess_portfolio_risk(positions, prices, cash)


def calculate_position_sizes(portfolio_value: float, signals: Dict[str, Dict[str, Any]], 
                           method: str = "fixed_fractional", risk_per_trade: float = 0.02) -> Dict[str, Any]:
    """Calculate optimal position sizes."""
    method_enum = PositionSizingMethod(method)
    return position_sizing.calculate_position_sizes(portfolio_value, signals, method_enum, risk_per_trade)


def get_portfolio_risk_report(positions: Dict[str, float], prices: Dict[str, pd.DataFrame], cash: float = 0.0) -> Dict[str, Any]:
    """Generate comprehensive portfolio risk report."""
    try:
        # Calculate portfolio metrics
        portfolio_metrics = risk_analytics.calculate_portfolio_metrics(positions, prices, cash)
        
        # Generate visualizations
        visualizations = {}
        
        # Risk metrics chart
        risk_metrics = portfolio_metrics.risk_metrics
        if risk_metrics:
            fig = go.Figure()
            
            metrics_names = ['volatility', 'var_95', 'expected_shortfall_95', 'max_drawdown']
            metrics_values = [risk_metrics.get(metric, 0) for metric in metrics_names]
            
            fig.add_trace(go.Bar(
                x=metrics_names,
                y=metrics_values,
                text=[f"{v:.3f}" for v in metrics_values],
                textposition='auto'
            ))
            
            fig.update_layout(
                title="Portfolio Risk Metrics",
                xaxis_title="Metric",
                yaxis_title="Value"
            )
            
            visualizations["risk_metrics"] = fig.to_html(include_plotlyjs='cdn')
        
        # Weight distribution chart
        if portfolio_metrics.weights:
            fig2 = go.Figure(data=[go.Pie(
                labels=list(portfolio_metrics.weights.keys()),
                values=list(portfolio_metrics.weights.values()),
                title="Portfolio Weight Distribution"
            )])
            
            visualizations["weight_distribution"] = fig2.to_html(include_plotlyjs='cdn')
        
        return {
            "portfolio_metrics": portfolio_metrics.to_dict(),
            "visualizations": visualizations,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating risk report: {e}")
        return {}
