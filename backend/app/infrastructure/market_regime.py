"""
Market regime detection for adaptive trading strategies.
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache
from app.infrastructure.metrics import get_metrics

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime types."""
    BULL_MARKET = "bull_market"
    BEAR_MARKET = "bear_market"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    TRENDING = "trending"
    MEAN_REVERTING = "mean_reverting"
    CRISIS = "crisis"
    RECOVERY = "recovery"


class DetectionMethod(Enum):
    """Regime detection methods."""
    MARKOWITZ_REGIMES = "markowitz_regimes"
    MOMENTUM_REGIMES = "momentum_regimes"
    VOLATILITY_REGIMES = "volatility_regimes"
    CLUSTERING = "clustering"
    HIDDEN_MARKOV = "hidden_markov"
    BAYESIAN_CHANGE_POINT = "bayesian_change_point"
    MACHINE_LEARNING = "machine_learning"


@dataclass
class RegimeState:
    """Market regime state information."""
    regime: MarketRegime
    probability: float
    start_date: datetime
    end_date: Optional[datetime]
    duration_days: int
    characteristics: Dict[str, float]
    confidence: float
    transition_probabilities: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['regime'] = self.regime.value
        result['start_date'] = self.start_date.isoformat()
        if self.end_date:
            result['end_date'] = self.end_date.isoformat()
        return result


@dataclass
class RegimeDetectionResult:
    """Result of regime detection analysis."""
    method: DetectionMethod
    regimes: List[RegimeState]
    current_regime: Optional[RegimeState]
    transition_matrix: Dict[str, Dict[str, float]]
    performance_metrics: Dict[str, float]
    detection_confidence: float
    parameters: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['method'] = self.method.value
        result['regimes'] = [regime.to_dict() for regime in self.regimes]
        if self.current_regime:
            result['current_regime'] = self.current_regime.to_dict()
        return result


class MarketRegimeDetector(LoggerMixin):
    """Market regime detection using multiple methods."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.scaler = StandardScaler()
        self.regime_models = {}
    
    def detect_regimes(self, market_data: pd.DataFrame, method: DetectionMethod = DetectionMethod.CLUSTERING,
                      n_regimes: int = 4, window_size: int = 60) -> RegimeDetectionResult:
        """Detect market regimes using specified method."""
        try:
            if market_data.empty:
                raise ValueError("Market data is empty")
            
            # Preprocess data
            features = self._extract_features(market_data, window_size)
            
            if features.empty:
                raise ValueError("No features extracted from market data")
            
            # Detect regimes based on method
            if method == DetectionMethod.CLUSTERING:
                result = self._detect_regimes_clustering(features, market_data, n_regimes)
            elif method == DetectionMethod.MOMENTUM_REGIMES:
                result = self._detect_momentum_regimes(market_data, window_size)
            elif method == DetectionMethod.VOLATILITY_REGIMES:
                result = self._detect_volatility_regimes(market_data, window_size)
            elif method == DetectionMethod.MARKOWITZ_REGIMES:
                result = self._detect_markowitz_regimes(market_data, window_size)
            elif method == DetectionMethod.MACHINE_LEARNING:
                result = self._detect_ml_regimes(features, market_data, n_regimes)
            else:
                raise ValueError(f"Unsupported detection method: {method}")
            
            # Calculate performance metrics
            result.performance_metrics = self._calculate_regime_performance(result, market_data)
            
            # Cache result
            cache_key = f"regime_detection:{method.value}:{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            self.cache.set(cache_key, result.to_dict(), ttl=3600)  # 1 hour TTL
            
            self.logger.info(f"Detected {len(result.regimes)} regimes using {method.value}")
            
            # Record metrics
            self.metrics.record_trading_signal(
                signal_type="regime_detection_completed",
                asset_symbol=f"method_{method.value}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error detecting regimes: {e}")
            raise
    
    def _extract_features(self, market_data: pd.DataFrame, window_size: int) -> pd.DataFrame:
        """Extract features for regime detection."""
        try:
            features = pd.DataFrame(index=market_data.index)
            
            # Price-based features
            features['returns'] = market_data['close'].pct_change()
            features['log_returns'] = np.log(market_data['close'] / market_data['close'].shift(1))
            
            # Volatility features
            features['volatility'] = features['returns'].rolling(window=window_size).std()
            features['volatility_ratio'] = features['volatility'] / features['volatility'].rolling(window=window_size*2).mean()
            
            # Momentum features
            for period in [5, 10, 20, 50]:
                features[f'momentum_{period}'] = market_data['close'].pct_change(period)
                features[f'momentum_abs_{period}'] = features[f'momentum_{period}'].abs()
            
            # Trend features
            features['price_trend'] = (market_data['close'] - market_data['close'].rolling(window=window_size).mean()) / market_data['close'].rolling(window=window_size).mean()
            
            # Volume features
            if 'volume' in market_data.columns:
                features['volume_ratio'] = market_data['volume'] / market_data['volume'].rolling(window=window_size).mean()
                features['volume_volatility'] = market_data['volume'].pct_change().rolling(window=window_size).std()
            
            # Range features
            features['high_low_ratio'] = (market_data['high'] / market_data['low']).rolling(window=window_size).mean()
            features['range_ratio'] = (market_data['high'] - market_data['low']) / market_data['close']
            
            # Moving average features
            for ma_period in [10, 20, 50]:
                features[f'ma_ratio_{ma_period}'] = market_data['close'] / market_data['close'].rolling(ma_period).mean()
            
            # RSI and other indicators
            delta = market_data['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = 100 - (100 / (1 + gain / loss))
            features['rsi'] = rs
            
            # Remove NaN values
            features = features.fillna(method='ffill').fillna(method='bfill').fillna(0)
            
            return features
            
        except Exception as e:
            self.logger.error(f"Error extracting features: {e}")
            return pd.DataFrame()
    
    def _detect_regimes_clustering(self, features: pd.DataFrame, market_data: pd.DataFrame, n_regimes: int) -> RegimeDetectionResult:
        """Detect regimes using clustering."""
        try:
            # Scale features
            scaled_features = self.scaler.fit_transform(features)
            
            # Apply PCA for dimensionality reduction
            pca = PCA(n_components=min(10, scaled_features.shape[1]))
            pca_features = pca.fit_transform(scaled_features)
            
            # K-means clustering
            kmeans = KMeans(n_clusters=n_regimes, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(pca_features)
            
            # Create regime states
            regimes = self._create_regimes_from_clusters(cluster_labels, market_data)
            
            # Determine current regime
            current_regime = regimes[-1] if regimes else None
            
            # Calculate transition matrix
            transition_matrix = self._calculate_transition_matrix(cluster_labels, n_regimes)
            
            # Classify regimes
            classified_regimes = self._classify_regimes(regimes, market_data)
            
            return RegimeDetectionResult(
                method=DetectionMethod.CLUSTERING,
                regimes=classified_regimes,
                current_regime=current_regime,
                transition_matrix=transition_matrix,
                performance_metrics={},
                detection_confidence=0.8,  # Placeholder
                parameters={
                    'n_regimes': n_regimes,
                    'pca_components': pca.n_components_,
                    'inertia': kmeans.inertia_
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error in clustering detection: {e}")
            raise
    
    def _detect_momentum_regimes(self, market_data: pd.DataFrame, window_size: int) -> RegimeDetectionResult:
        """Detect regimes based on momentum."""
        try:
            returns = market_data['close'].pct_change()
            
            # Calculate momentum indicators
            short_momentum = returns.rolling(window=10).mean()
            long_momentum = returns.rolling(window=50).mean()
            
            # Classify regimes based on momentum
            regimes = []
            regime_labels = []
            
            for i in range(len(market_data)):
                if i < window_size:
                    regime = MarketRegime.SIDEWAYS
                else:
                    short_mom = short_momentum.iloc[i]
                    long_mom = long_momentum.iloc[i]
                    
                    if short_mom > 0.02 and long_mom > 0.01:
                        regime = MarketRegime.BULL_MARKET
                    elif short_mom < -0.02 and long_mom < -0.01:
                        regime = MarketRegime.BEAR_MARKET
                    elif abs(short_mom) < 0.005:
                        regime = MarketRegime.SIDEWAYS
                    elif short_mom > 0 and long_mom < 0:
                        regime = MarketRegime.MEAN_REVERTING
                    else:
                        regime = MarketRegime.TRENDING
                
                regime_labels.append(regime)
                
                # Create regime state
                if i > 0:
                    last_regime = regimes[-1]
                    if last_regime.regime == regime:
                        # Extend current regime
                        last_regime.duration_days += 1
                        last_regime.end_date = market_data.index[i]
                    else:
                        # New regime
                        regime_state = RegimeState(
                            regime=regime,
                            probability=1.0,
                            start_date=market_data.index[i-1],
                            end_date=market_data.index[i],
                            duration_days=1,
                            characteristics={'momentum': short_mom},
                            confidence=0.7,
                            transition_probabilities={}
                        )
                        regimes.append(regime_state)
            
            current_regime = regimes[-1] if regimes else None
            
            return RegimeDetectionResult(
                method=DetectionMethod.MOMENTUM_REGIMES,
                regimes=regimes,
                current_regime=current_regime,
                transition_matrix={},
                performance_metrics={},
                detection_confidence=0.7,
                parameters={'window_size': window_size}
            )
            
        except Exception as e:
            self.logger.error(f"Error in momentum detection: {e}")
            raise
    
    def _detect_volatility_regimes(self, market_data: pd.DataFrame, window_size: int) -> RegimeDetectionResult:
        """Detect regimes based on volatility."""
        try:
            returns = market_data['close'].pct_change()
            volatility = returns.rolling(window=window_size).std()
            
            # Classify regimes based on volatility
            regimes = []
            regime_labels = []
            
            volatility_threshold = volatility.median()
            
            for i in range(len(market_data)):
                if i < window_size:
                    regime = MarketRegime.LOW_VOLATILITY
                else:
                    current_vol = volatility.iloc[i]
                    
                    if current_vol > volatility_threshold * 2:
                        regime = MarketRegime.HIGH_VOLATILITY
                    elif current_vol > volatility_threshold * 1.5:
                        regime = MarketRegime.CRISIS
                    elif current_vol < volatility_threshold * 0.5:
                        regime = MarketRegime.LOW_VOLATILITY
                    else:
                        regime = MarketRegime.SIDEWAYS
                
                regime_labels.append(regime)
                
                # Create regime state
                if i > 0:
                    last_regime = regimes[-1]
                    if last_regime.regime == regime:
                        # Extend current regime
                        last_regime.duration_days += 1
                        last_regime.end_date = market_data.index[i]
                    else:
                        # New regime
                        regime_state = RegimeState(
                            regime=regime,
                            probability=1.0,
                            start_date=market_data.index[i-1],
                            end_date=market_data.index[i],
                            duration_days=1,
                            characteristics={'volatility': current_vol},
                            confidence=0.6,
                            transition_probabilities={}
                        )
                        regimes.append(regime_state)
            
            current_regime = regimes[-1] if regimes else None
            
            return RegimeDetectionResult(
                method=DetectionMethod.VOLATILITY_REGIMES,
                regimes=regimes,
                current_regime=current_regime,
                transition_matrix={},
                performance_metrics={},
                detection_confidence=0.6,
                parameters={'window_size': window_size}
            )
            
        except Exception as e:
            self.logger.error(f"Error in volatility detection: {e}")
            raise
    
    def _detect_markowitz_regimes(self, market_data: pd.DataFrame, window_size: int) -> RegimeDetectionResult:
        """Detect regimes using Markowitz-style analysis."""
        try:
            returns = market_data['close'].pct_change()
            
            # Calculate rolling statistics
            rolling_mean = returns.rolling(window=window_size).mean()
            rolling_std = returns.rolling(window=window_size).std()
            rolling_sharpe = rolling_mean / rolling_std
            
            # Classify regimes
            regimes = []
            
            for i in range(len(market_data)):
                if i < window_size:
                    regime = MarketRegime.SIDEWAYS
                else:
                    mean_ret = rolling_mean.iloc[i]
                    vol = rolling_std.iloc[i]
                    sharpe = rolling_sharpe.iloc[i]
                    
                    if mean_ret > 0.01 and sharpe > 1.0:
                        regime = MarketRegime.BULL_MARKET
                    elif mean_ret < -0.01 and sharpe < -1.0:
                        regime = MarketRegime.BEAR_MARKET
                    elif vol > rolling_std.mean() * 2:
                        regime = MarketRegime.CRISIS
                    elif abs(mean_ret) < 0.005:
                        regime = MarketRegime.SIDEWAYS
                    else:
                        regime = MarketRegime.RECOVERY
                
                # Create regime state
                if i > 0:
                    last_regime = regimes[-1]
                    if last_regime.regime == regime:
                        # Extend current regime
                        last_regime.duration_days += 1
                        last_regime.end_date = market_data.index[i]
                    else:
                        # New regime
                        regime_state = RegimeState(
                            regime=regime,
                            probability=1.0,
                            start_date=market_data.index[i-1],
                            end_date=market_data.index[i],
                            duration_days=1,
                            characteristics={
                                'mean_return': mean_ret,
                                'volatility': vol,
                                'sharpe_ratio': sharpe
                            },
                            confidence=0.75,
                            transition_probabilities={}
                        )
                        regimes.append(regime_state)
            
            current_regime = regimes[-1] if regimes else None
            
            return RegimeDetectionResult(
                method=DetectionMethod.MARKOWITZ_REGIMES,
                regimes=regimes,
                current_regime=current_regime,
                transition_matrix={},
                performance_metrics={},
                detection_confidence=0.75,
                parameters={'window_size': window_size}
            )
            
        except Exception as e:
            self.logger.error(f"Error in Markowitz detection: {e}")
            raise
    
    def _detect_ml_regimes(self, features: pd.DataFrame, market_data: pd.DataFrame, n_regimes: int) -> RegimeDetectionResult:
        """Detect regimes using machine learning (Gaussian Mixture Model)."""
        try:
            # Scale features
            scaled_features = self.scaler.fit_transform(features)
            
            # Apply PCA
            pca = PCA(n_components=min(5, scaled_features.shape[1]))
            pca_features = pca.fit_transform(scaled_features)
            
            # Gaussian Mixture Model
            gmm = GaussianMixture(n_components=n_regimes, random_state=42)
            cluster_labels = gmm.fit_predict(pca_features)
            
            # Get probabilities
            probabilities = gmm.predict_proba(pca_features)
            
            # Create regime states
            regimes = self._create_regimes_from_clusters(cluster_labels, market_data)
            
            # Add probabilities
            for i, regime in enumerate(regimes):
                if i < len(probabilities):
                    regime.probability = np.max(probabilities[i])
                    regime.confidence = regime.probability
            
            current_regime = regimes[-1] if regimes else None
            
            # Calculate transition matrix
            transition_matrix = self._calculate_transition_matrix(cluster_labels, n_regimes)
            
            return RegimeDetectionResult(
                method=DetectionMethod.MACHINE_LEARNING,
                regimes=regimes,
                current_regime=current_regime,
                transition_matrix=transition_matrix,
                performance_metrics={},
                detection_confidence=0.85,
                parameters={
                    'n_regimes': n_regimes,
                    'pca_components': pca.n_components_,
                    'aic': gmm.aic(),
                    'bic': gmm.bic()
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error in ML detection: {e}")
            raise
    
    def _create_regimes_from_clusters(self, cluster_labels: np.ndarray, market_data: pd.DataFrame) -> List[RegimeState]:
        """Create regime states from cluster labels."""
        try:
            regimes = []
            
            for i in range(len(cluster_labels)):
                current_label = cluster_labels[i]
                
                if i == 0:
                    # First regime
                    regime_state = RegimeState(
                        regime=MarketRegime.SIDEWAYS,  # Will be classified later
                        probability=1.0,
                        start_date=market_data.index[i],
                        end_date=market_data.index[i],
                        duration_days=1,
                        characteristics={},
                        confidence=0.5,
                        transition_probabilities={}
                    )
                    regimes.append(regime_state)
                else:
                    last_regime = regimes[-1]
                    
                    if cluster_labels[i-1] == current_label:
                        # Same regime, extend duration
                        last_regime.duration_days += 1
                        last_regime.end_date = market_data.index[i]
                    else:
                        # New regime
                        regime_state = RegimeState(
                            regime=MarketRegime.SIDEWAYS,  # Will be classified later
                            probability=1.0,
                            start_date=market_data.index[i-1],
                            end_date=market_data.index[i],
                            duration_days=1,
                            characteristics={},
                            confidence=0.5,
                            transition_probabilities={}
                        )
                        regimes.append(regime_state)
            
            return regimes
            
        except Exception as e:
            self.logger.error(f"Error creating regimes from clusters: {e}")
            return []
    
    def _classify_regimes(self, regimes: List[RegimeState], market_data: pd.DataFrame) -> List[RegimeState]:
        """Classify regimes based on their characteristics."""
        try:
            for regime in regimes:
                # Get data for regime period
                regime_data = market_data.loc[regime.start_date:regime.end_date]
                
                if regime_data.empty:
                    continue
                
                returns = regime_data['close'].pct_change().dropna()
                
                if len(returns) == 0:
                    regime.regime = MarketRegime.SIDEWAYS
                    continue
                
                # Calculate characteristics
                mean_return = returns.mean()
                volatility = returns.std()
                total_return = (1 + returns).prod() - 1
                
                # Classify based on characteristics
                if mean_return > 0.01 and total_return > 0.05:
                    regime.regime = MarketRegime.BULL_MARKET
                elif mean_return < -0.01 and total_return < -0.05:
                    regime.regime = MarketRegime.BEAR_MARKET
                elif volatility > returns.std() * 2:
                    regime.regime = MarketRegime.HIGH_VOLATILITY
                elif volatility < returns.std() * 0.5:
                    regime.regime = MarketRegime.LOW_VOLATILITY
                elif abs(mean_return) < 0.005:
                    regime.regime = MarketRegime.SIDEWAYS
                else:
                    regime.regime = MarketRegime.TRENDING
                
                # Update characteristics
                regime.characteristics = {
                    'mean_return': mean_return,
                    'volatility': volatility,
                    'total_return': total_return,
                    'sharpe_ratio': mean_return / volatility if volatility > 0 else 0
                }
            
            return regimes
            
        except Exception as e:
            self.logger.error(f"Error classifying regimes: {e}")
            return regimes
    
    def _calculate_transition_matrix(self, labels: np.ndarray, n_regimes: int) -> Dict[str, Dict[str, float]]:
        """Calculate transition probability matrix."""
        try:
            transition_matrix = {}
            
            for i in range(n_regimes):
                transition_matrix[f'regime_{i}'] = {}
                
                # Count transitions from regime i
                transitions_from_i = []
                for j in range(len(labels) - 1):
                    if labels[j] == i:
                        next_label = labels[j + 1]
                        transitions_from_i.append(next_label)
                
                if transitions_from_i:
                    # Calculate probabilities
                    total_transitions = len(transitions_from_i)
                    for j in range(n_regimes):
                        count = transitions_from_i.count(j)
                        transition_matrix[f'regime_{i}'][f'regime_{j}'] = count / total_transitions
                else:
                    # No transitions, equal probability
                    for j in range(n_regimes):
                        transition_matrix[f'regime_{i}'][f'regime_{j}'] = 1.0 / n_regimes
            
            return transition_matrix
            
        except Exception as e:
            self.logger.error(f"Error calculating transition matrix: {e}")
            return {}
    
    def _calculate_regime_performance(self, result: RegimeDetectionResult, market_data: pd.DataFrame) -> Dict[str, float]:
        """Calculate performance metrics for each regime."""
        try:
            performance_metrics = {}
            
            for regime in result.regimes:
                # Get data for regime period
                regime_data = market_data.loc[regime.start_date:regime.end_date]
                
                if regime_data.empty:
                    continue
                
                returns = regime_data['close'].pct_change().dropna()
                
                if len(returns) == 0:
                    continue
                
                # Calculate performance metrics
                total_return = (1 + returns).prod() - 1
                volatility = returns.std()
                sharpe_ratio = returns.mean() / volatility if volatility > 0 else 0
                max_drawdown = self._calculate_max_drawdown(returns.values)
                win_rate = (returns > 0).mean()
                
                performance_key = f"{regime.regime.value}_performance"
                performance_metrics[performance_key] = {
                    'total_return': total_return,
                    'volatility': volatility,
                    'sharpe_ratio': sharpe_ratio,
                    'max_drawdown': max_drawdown,
                    'win_rate': win_rate,
                    'duration_days': regime.duration_days
                }
            
            return performance_metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating regime performance: {e}")
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
    
    def predict_regime_transition(self, current_regime: MarketRegime, transition_matrix: Dict[str, Dict[str, float]]) -> Dict[str, float]:
        """Predict next regime based on transition matrix."""
        try:
            predictions = {}
            
            current_key = f"regime_{list(MarketRegime).index(current_regime)}"
            
            if current_key in transition_matrix:
                for regime_key, probability in transition_matrix[current_key].items():
                    regime_name = regime_key.replace("regime_", "")
                    predictions[regime_name] = probability
            
            return predictions
            
        except Exception as e:
            self.logger.error(f"Error predicting regime transition: {e}")
            return {}
    
    def get_regime_summary(self, result: RegimeDetectionResult) -> Dict[str, Any]:
        """Generate summary of regime detection results."""
        try:
            summary = {
                "method": result.method.value,
                "total_regimes": len(result.regimes),
                "current_regime": result.current_regime.regime.value if result.current_regime else None,
                "detection_confidence": result.detection_confidence,
                "regime_distribution": {},
                "average_duration": 0,
                "performance_by_regime": {}
            }
            
            # Calculate regime distribution
            regime_counts = {}
            total_duration = 0
            
            for regime in result.regimes:
                regime_name = regime.regime.value
                regime_counts[regime_name] = regime_counts.get(regime_name, 0) + 1
                total_duration += regime.duration_days
            
            for regime_name, count in regime_counts.items():
                summary["regime_distribution"][regime_name] = {
                    "count": count,
                    "percentage": (count / len(result.regimes)) * 100
                }
            
            # Calculate average duration
            if total_duration > 0:
                summary["average_duration"] = total_duration / len(result.regimes)
            
            # Add performance metrics
            summary["performance_by_regime"] = result.performance_metrics
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error generating regime summary: {e}")
            return {}


# Global instance
market_regime_detector = MarketRegimeDetector()


def get_market_regime_detector() -> MarketRegimeDetector:
    """Get market regime detector instance."""
    return market_regime_detector


# Utility functions
def detect_market_regimes(market_data: pd.DataFrame, method: str = "clustering", 
                           n_regimes: int = 4, window_size: int = 60) -> Dict[str, Any]:
    """Detect market regimes in the provided data."""
    try:
        method_enum = DetectionMethod(method)
        result = market_regime_detector.detect_regimes(market_data, method_enum, n_regimes, window_size)
        
        return {
            "detection_result": result.to_dict(),
            "summary": market_regime_detector.get_regime_summary(result),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error detecting market regimes: {e}")
        return {}


def get_current_regime(market_data: pd.DataFrame, method: str = "clustering") -> Optional[Dict[str, Any]]:
    """Get current market regime."""
    try:
        method_enum = DetectionMethod(method)
        result = market_regime_detector.detect_regimes(market_data, method_enum)
        
        if result.current_regime:
            return {
                "regime": result.current_regime.regime.value,
                "probability": result.current_regime.probability,
                "confidence": result.current_regime.confidence,
                "characteristics": result.current_regime.characteristics,
                "duration_days": result.current_regime.duration_days,
                "start_date": result.current_regime.start_date.isoformat(),
                "method": method
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting current regime: {e}")
        return None


# Decorators for regime-aware trading
def regime_aware_trading(regime_method: str = "clustering"):
    """Decorator for regime-aware trading strategies."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # This would integrate with trading strategies
            # For now, just log the intent
            logger.info(f"Regime-aware trading requested with method: {regime_method}")
            return func(*args, **kwargs)
        return wrapper
    return decorator
