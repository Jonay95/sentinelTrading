"""
Feature engineering framework for Sentinel Trading ML models.
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
from sklearn.decomposition import PCA
from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_classif
import talib

from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache
from app.infrastructure.metrics import get_metrics

logger = logging.getLogger(__name__)


class FeatureType(Enum):
    """Types of features."""
    PRICE_BASED = "price_based"
    VOLUME_BASED = "volume_based"
    TECHNICAL_INDICATORS = "technical_indicators"
    STATISTICAL = "statistical"
    TIME_BASED = "time_based"
    SENTIMENT = "sentiment"
    MACRO = "macro"
    CUSTOM = "custom"


class ScalingMethod(Enum):
    """Feature scaling methods."""
    STANDARD = "standard"
    MINMAX = "minmax"
    ROBUST = "robust"
    NONE = "none"


@dataclass
class FeatureConfig:
    """Configuration for feature engineering."""
    window_sizes: List[int] = None
    lags: List[int] = None
    technical_indicators: List[str] = None
    scaling_method: ScalingMethod = ScalingMethod.STANDARD
    pca_components: Optional[int] = None
    feature_selection_k: Optional[int] = None
    include_sentiment: bool = True
    include_time_features: bool = True
    
    def __post_init__(self):
        if self.window_sizes is None:
            self.window_sizes = [5, 10, 20, 50]
        if self.lags is None:
            self.lags = [1, 2, 3, 5, 10]
        if self.technical_indicators is None:
            self.technical_indicators = [
                'sma', 'ema', 'rsi', 'macd', 'bollinger', 'stochastic', 'atr', 'obv'
            ]


class FeatureEngineer(LoggerMixin):
    """Feature engineering framework for financial data."""
    
    def __init__(self, config: FeatureConfig = None):
        self.config = config or FeatureConfig()
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.scalers = {}
        self.feature_names = []
        self.pca = None
        self.feature_selector = None
    
    def engineer_features(self, df: pd.DataFrame, fit_transform: bool = True) -> pd.DataFrame:
        """Engineer features from raw price data."""
        try:
            if df.empty:
                raise ValueError("Input DataFrame is empty")
            
            # Ensure required columns exist
            required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"Missing required columns: {missing_columns}")
            
            # Sort by timestamp
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Create feature DataFrame
            features_df = pd.DataFrame(index=df.index)
            features_df['timestamp'] = df['timestamp']
            
            # Add basic price features
            self._add_price_features(features_df, df)
            
            # Add volume features
            self._add_volume_features(features_df, df)
            
            # Add technical indicators
            self._add_technical_indicators(features_df, df)
            
            # Add statistical features
            self._add_statistical_features(features_df, df)
            
            # Add time-based features
            if self.config.include_time_features:
                self._add_time_features(features_df, df)
            
            # Add lag features
            self._add_lag_features(features_df, df)
            
            # Add rolling window features
            self._add_rolling_features(features_df, df)
            
            # Remove timestamp column for ML
            feature_columns = [col for col in features_df.columns if col != 'timestamp']
            features = features_df[feature_columns]
            
            # Handle missing values
            features = self._handle_missing_values(features)
            
            # Scale features
            features = self._scale_features(features, fit_transform)
            
            # Apply PCA if configured
            if self.config.pca_components:
                features = self._apply_pca(features, fit_transform)
            
            # Apply feature selection if configured
            if self.config.feature_selection_k:
                features = self._apply_feature_selection(features, fit_transform)
            
            # Store feature names
            self.feature_names = features.columns.tolist()
            
            # Cache feature config
            cache_key = "feature_engineering_config"
            self.cache.set(cache_key, self.config.__dict__, ttl=3600)
            
            self.logger.info(f"Engineered {len(features.columns)} features from {len(df)} rows")
            
            # Record metrics
            self.metrics.record_trading_signal(
                signal_type="features_engineered",
                asset_symbol=f"features_{len(features.columns)}"
            )
            
            return features
            
        except Exception as e:
            self.logger.error(f"Error engineering features: {e}")
            raise
    
    def _add_price_features(self, features_df: pd.DataFrame, df: pd.DataFrame):
        """Add basic price-based features."""
        try:
            # Price changes
            features_df['price_change'] = df['close'].pct_change()
            features_df['price_change_abs'] = features_df['price_change'].abs()
            
            # High-Low spread
            features_df['hl_spread'] = df['high'] - df['low']
            features_df['hl_spread_pct'] = features_df['hl_spread'] / df['close']
            
            # Open-Close spread
            features_df['oc_spread'] = df['close'] - df['open']
            features_df['oc_spread_pct'] = features_df['oc_spread'] / df['open']
            
            # Typical price
            features_df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
            
            # Weighted price
            features_df['weighted_price'] = (df['high'] + df['low'] + 2 * df['close']) / 4
            
            # Price position in range
            features_df['price_position'] = (df['close'] - df['low']) / (df['high'] - df['low'])
            
        except Exception as e:
            self.logger.error(f"Error adding price features: {e}")
    
    def _add_volume_features(self, features_df: pd.DataFrame, df: pd.DataFrame):
        """Add volume-based features."""
        try:
            # Volume change
            features_df['volume_change'] = df['volume'].pct_change()
            features_df['volume_change_abs'] = features_df['volume_change'].abs()
            
            # Volume-weighted average price (VWAP)
            features_df['vwap'] = (df['volume'] * df['close']).rolling(window=20).sum() / df['volume'].rolling(window=20).sum()
            
            # Volume ratio to moving average
            volume_ma = df['volume'].rolling(window=20).mean()
            features_df['volume_ratio'] = df['volume'] / volume_ma
            
            # Price-Volume correlation (rolling)
            features_df['price_volume_corr'] = df['close'].rolling(window=20).corr(df['volume'])
            
        except Exception as e:
            self.logger.error(f"Error adding volume features: {e}")
    
    def _add_technical_indicators(self, features_df: pd.DataFrame, df: pd.DataFrame):
        """Add technical indicator features."""
        try:
            for indicator in self.config.technical_indicators:
                if indicator == 'sma':
                    # Simple Moving Averages
                    for window in [5, 10, 20, 50]:
                        features_df[f'sma_{window}'] = talib.SMA(df['close'], timeperiod=window)
                        features_df[f'sma_{window}_ratio'] = df['close'] / features_df[f'sma_{window}']
                
                elif indicator == 'ema':
                    # Exponential Moving Averages
                    for window in [5, 10, 20, 50]:
                        features_df[f'ema_{window}'] = talib.EMA(df['close'], timeperiod=window)
                        features_df[f'ema_{window}_ratio'] = df['close'] / features_df[f'ema_{window}']
                
                elif indicator == 'rsi':
                    # Relative Strength Index
                    features_df['rsi_14'] = talib.RSI(df['close'], timeperiod=14)
                    features_df['rsi_7'] = talib.RSI(df['close'], timeperiod=7)
                
                elif indicator == 'macd':
                    # MACD
                    macd, macd_signal, macd_hist = talib.MACD(df['close'])
                    features_df['macd'] = macd
                    features_df['macd_signal'] = macd_signal
                    features_df['macd_histogram'] = macd_hist
                
                elif indicator == 'bollinger':
                    # Bollinger Bands
                    bb_upper, bb_middle, bb_lower = talib.BBANDS(df['close'])
                    features_df['bb_upper'] = bb_upper
                    features_df['bb_middle'] = bb_middle
                    features_df['bb_lower'] = bb_lower
                    features_df['bb_width'] = (bb_upper - bb_lower) / bb_middle
                    features_df['bb_position'] = (df['close'] - bb_lower) / (bb_upper - bb_lower)
                
                elif indicator == 'stochastic':
                    # Stochastic Oscillator
                    slowk, slowd = talib.STOCH(df['high'], df['low'], df['close'])
                    features_df['stoch_k'] = slowk
                    features_df['stoch_d'] = slowd
                
                elif indicator == 'atr':
                    # Average True Range
                    features_df['atr_14'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
                    features_df['atr_ratio'] = features_df['atr_14'] / df['close']
                
                elif indicator == 'obv':
                    # On-Balance Volume
                    features_df['obv'] = talib.OBV(df['close'], df['volume'])
                    features_df['obv_sma'] = talib.SMA(features_df['obv'], timeperiod=10)
                
        except Exception as e:
            self.logger.error(f"Error adding technical indicators: {e}")
    
    def _add_statistical_features(self, features_df: pd.DataFrame, df: pd.DataFrame):
        """Add statistical features."""
        try:
            # Rolling statistics
            for window in [5, 10, 20]:
                # Mean and std
                features_df[f'close_mean_{window}'] = df['close'].rolling(window).mean()
                features_df[f'close_std_{window}'] = df['close'].rolling(window).std()
                features_df[f'close_zscore_{window}'] = (df['close'] - features_df[f'close_mean_{window}']) / features_df[f'close_std_{window}']
                
                # Min and max
                features_df[f'close_min_{window}'] = df['close'].rolling(window).min()
                features_df[f'close_max_{window}'] = df['close'].rolling(window).max()
                features_df[f'close_range_{window}'] = features_df[f'close_max_{window}'] - features_df[f'close_min_{window}']
                
                # Quantiles
                features_df[f'close_q25_{window}'] = df['close'].rolling(window).quantile(0.25)
                features_df[f'close_q75_{window}'] = df['close'].rolling(window).quantile(0.75)
                features_df[f'close_iqr_{window}'] = features_df[f'close_q75_{window}'] - features_df[f'close_q25_{window}']
            
            # Skewness and kurtosis
            features_df['close_skew_20'] = df['close'].rolling(window=20).skew()
            features_df['close_kurt_20'] = df['close'].rolling(window=20).kurt()
            
            # Price momentum
            for period in [1, 3, 5, 10]:
                features_df[f'momentum_{period}'] = df['close'].pct_change(period)
                features_df[f'momentum_{period}_abs'] = features_df[f'momentum_{period}'].abs()
            
        except Exception as e:
            self.logger.error(f"Error adding statistical features: {e}")
    
    def _add_time_features(self, features_df: pd.DataFrame, df: pd.DataFrame):
        """Add time-based features."""
        try:
            # Convert timestamp to datetime if needed
            timestamps = pd.to_datetime(df['timestamp'])
            
            # Basic time features
            features_df['hour'] = timestamps.dt.hour
            features_df['day_of_week'] = timestamps.dt.dayofweek
            features_df['day_of_month'] = timestamps.dt.day
            features_df['month'] = timestamps.dt.month
            features_df['quarter'] = timestamps.dt.quarter
            
            # Cyclical encoding
            features_df['hour_sin'] = np.sin(2 * np.pi * features_df['hour'] / 24)
            features_df['hour_cos'] = np.cos(2 * np.pi * features_df['hour'] / 24)
            features_df['day_sin'] = np.sin(2 * np.pi * features_df['day_of_week'] / 7)
            features_df['day_cos'] = np.cos(2 * np.pi * features_df['day_of_week'] / 7)
            features_df['month_sin'] = np.sin(2 * np.pi * features_df['month'] / 12)
            features_df['month_cos'] = np.cos(2 * np.pi * features_df['month'] / 12)
            
            # Market session indicators (assuming trading hours 9:30-16:00)
            features_df['is_market_hours'] = ((timestamps.dt.hour >= 9) & (timestamps.dt.hour < 16)).astype(int)
            features_df['is_pre_market'] = ((timestamps.dt.hour >= 4) & (timestamps.dt.hour < 9)).astype(int)
            features_df['is_after_hours'] = ((timestamps.dt.hour >= 16) & (timestamps.dt.hour < 20)).astype(int)
            
        except Exception as e:
            self.logger.error(f"Error adding time features: {e}")
    
    def _add_lag_features(self, features_df: pd.DataFrame, df: pd.DataFrame):
        """Add lag features."""
        try:
            # Price lags
            for lag in self.config.lags:
                features_df[f'close_lag_{lag}'] = df['close'].shift(lag)
                features_df[f'volume_lag_{lag}'] = df['volume'].shift(lag)
                features_df[f'price_change_lag_{lag}'] = features_df['price_change'].shift(lag)
            
        except Exception as e:
            self.logger.error(f"Error adding lag features: {e}")
    
    def _add_rolling_features(self, features_df: pd.DataFrame, df: pd.DataFrame):
        """Add rolling window features."""
        try:
            for window in self.config.window_sizes:
                # Rolling returns
                features_df[f'return_mean_{window}'] = features_df['price_change'].rolling(window).mean()
                features_df[f'return_std_{window}'] = features_df['price_change'].rolling(window).std()
                features_df[f'return_skew_{window}'] = features_df['price_change'].rolling(window).skew()
                
                # Rolling volume features
                features_df[f'volume_mean_{window}'] = df['volume'].rolling(window).mean()
                features_df[f'volume_std_{window}'] = df['volume'].rolling(window).std()
                
                # Rolling price features
                features_df[f'high_low_ratio_{window}'] = (df['high'].rolling(window).max() / df['low'].rolling(window).min())
                features_df[f'price_trend_{window}'] = (df['close'] / df['close'].shift(window) - 1)
                
        except Exception as e:
            self.logger.error(f"Error adding rolling features: {e}")
    
    def _handle_missing_values(self, features: pd.DataFrame) -> pd.DataFrame:
        """Handle missing values in features."""
        try:
            # Forward fill for time series
            features = features.fillna(method='ffill')
            
            # Backward fill for remaining NaNs
            features = features.fillna(method='bfill')
            
            # Fill remaining NaNs with 0
            features = features.fillna(0)
            
            return features
            
        except Exception as e:
            self.logger.error(f"Error handling missing values: {e}")
            return features
    
    def _scale_features(self, features: pd.DataFrame, fit_transform: bool) -> pd.DataFrame:
        """Scale features."""
        try:
            if self.config.scaling_method == ScalingMethod.NONE:
                return features
            
            # Choose scaler
            if self.config.scaling_method == ScalingMethod.STANDARD:
                scaler = StandardScaler()
            elif self.config.scaling_method == ScalingMethod.MINMAX:
                scaler = MinMaxScaler()
            elif self.config.scaling_method == ScalingMethod.ROBUST:
                scaler = RobustScaler()
            else:
                return features
            
            if fit_transform:
                # Fit and transform
                scaled_features = scaler.fit_transform(features)
                self.scalers['main'] = scaler
            else:
                # Only transform
                if 'main' in self.scalers:
                    scaled_features = self.scalers['main'].transform(features)
                else:
                    self.logger.warning("No fitted scaler found, using fit_transform")
                    scaled_features = scaler.fit_transform(features)
                    self.scalers['main'] = scaler
            
            # Convert back to DataFrame
            scaled_df = pd.DataFrame(scaled_features, columns=features.columns, index=features.index)
            
            return scaled_df
            
        except Exception as e:
            self.logger.error(f"Error scaling features: {e}")
            return features
    
    def _apply_pca(self, features: pd.DataFrame, fit_transform: bool) -> pd.DataFrame:
        """Apply PCA dimensionality reduction."""
        try:
            if fit_transform:
                # Fit and transform
                pca = PCA(n_components=self.config.pca_components)
                pca_features = pca.fit_transform(features)
                self.pca = pca
            else:
                # Only transform
                if self.pca is not None:
                    pca_features = self.pca.transform(features)
                else:
                    self.logger.warning("No fitted PCA found, using fit_transform")
                    pca = PCA(n_components=self.config.pca_components)
                    pca_features = pca.fit_transform(features)
                    self.pca = pca
            
            # Convert to DataFrame
            pca_columns = [f'pca_{i}' for i in range(pca_features.shape[1])]
            pca_df = pd.DataFrame(pca_features, columns=pca_columns, index=features.index)
            
            self.logger.info(f"Applied PCA: {features.shape[1]} -> {pca_features.shape[1]} features")
            
            return pca_df
            
        except Exception as e:
            self.logger.error(f"Error applying PCA: {e}")
            return features
    
    def _apply_feature_selection(self, features: pd.DataFrame, fit_transform: bool, target: pd.Series = None) -> pd.DataFrame:
        """Apply feature selection."""
        try:
            if target is None:
                self.logger.warning("No target provided for feature selection, skipping")
                return features
            
            if fit_transform:
                # Fit and transform
                selector = SelectKBest(score_func=f_classif, k=self.config.feature_selection_k)
                selected_features = selector.fit_transform(features, target)
                self.feature_selector = selector
            else:
                # Only transform
                if self.feature_selector is not None:
                    selected_features = self.feature_selector.transform(features)
                else:
                    self.logger.warning("No fitted feature selector found, using fit_transform")
                    selector = SelectKBest(score_func=f_classif, k=self.config.feature_selection_k)
                    selected_features = selector.fit_transform(features, target)
                    self.feature_selector = selector
            
            # Convert to DataFrame
            selected_columns = features.columns[self.feature_selector.get_support()]
            selected_df = pd.DataFrame(selected_features, columns=selected_columns, index=features.index)
            
            self.logger.info(f"Applied feature selection: {features.shape[1]} -> {selected_features.shape[1]} features")
            
            return selected_df
            
        except Exception as e:
            self.logger.error(f"Error applying feature selection: {e}")
            return features
    
    def get_feature_importance(self, features: pd.DataFrame, target: pd.Series) -> Dict[str, float]:
        """Get feature importance scores."""
        try:
            # Use mutual information for feature importance
            mi_scores = mutual_info_classif(features, target)
            
            importance_dict = dict(zip(features.columns, mi_scores))
            
            # Sort by importance
            sorted_importance = dict(
                sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)
            )
            
            return sorted_importance
            
        except Exception as e:
            self.logger.error(f"Error calculating feature importance: {e}")
            return {}
    
    def get_feature_stats(self) -> Dict[str, Any]:
        """Get feature engineering statistics."""
        try:
            return {
                "config": self.config.__dict__,
                "feature_names": self.feature_names,
                "feature_count": len(self.feature_names),
                "has_scaler": len(self.scalers) > 0,
                "has_pca": self.pca is not None,
                "has_feature_selector": self.feature_selector is not None,
                "pca_components": self.pca.n_components_ if self.pca else None,
                "selected_features": self.feature_selector.get_support().sum() if self.feature_selector else None
            }
            
        except Exception as e:
            self.logger.error(f"Error getting feature stats: {e}")
            return {}


class SentimentFeatureEngineer(LoggerMixin):
    """Feature engineer for sentiment data."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.cache = get_cache()
    
    def engineer_sentiment_features(self, news_df: pd.DataFrame, price_df: pd.DataFrame) -> pd.DataFrame:
        """Engineer sentiment features aligned with price data."""
        try:
            if news_df.empty or price_df.empty:
                return pd.DataFrame()
            
            # Ensure timestamp columns
            news_df['timestamp'] = pd.to_datetime(news_df['timestamp'])
            price_df['timestamp'] = pd.to_datetime(price_df['timestamp'])
            
            # Aggregate sentiment by time windows
            sentiment_features = self._aggregate_sentiment(news_df, price_df['timestamp'])
            
            # Merge with price data
            merged_df = price_df.merge(sentiment_features, on='timestamp', how='left')
            
            # Fill missing sentiment values
            sentiment_cols = [col for col in merged_df.columns if col.startswith('sentiment_')]
            merged_df[sentiment_cols] = merged_df[sentiment_cols].fillna(0)
            
            self.logger.info(f"Engineered {len(sentiment_cols)} sentiment features")
            
            return merged_df
            
        except Exception as e:
            self.logger.error(f"Error engineering sentiment features: {e}")
            return pd.DataFrame()
    
    def _aggregate_sentiment(self, news_df: pd.DataFrame, price_timestamps: pd.Series) -> pd.DataFrame:
        """Aggregate sentiment by time windows."""
        try:
            # Create time windows (e.g., hourly)
            news_df['time_window'] = news_df['timestamp'].dt.floor('H')
            
            # Aggregate sentiment by time window
            sentiment_agg = news_df.groupby('time_window').agg({
                'sentiment': ['mean', 'std', 'count'],
                'title': 'count'
            }).reset_index()
            
            # Flatten column names
            sentiment_agg.columns = ['timestamp', 'sentiment_mean', 'sentiment_std', 'sentiment_count', 'news_count']
            
            # Create features aligned with price timestamps
            sentiment_features = pd.DataFrame({'timestamp': price_timestamps})
            
            # Merge with aggregated sentiment
            sentiment_features = sentiment_features.merge(sentiment_agg, on='timestamp', how='left')
            
            # Fill missing values
            sentiment_features[['sentiment_mean', 'sentiment_std', 'sentiment_count', 'news_count']] = \
                sentiment_features[['sentiment_mean', 'sentiment_std', 'sentiment_count', 'news_count']].fillna(0)
            
            # Create additional features
            sentiment_features['sentiment_abs'] = sentiment_features['sentiment_mean'].abs()
            sentiment_features['sentiment_positive'] = (sentiment_features['sentiment_mean'] > 0).astype(int)
            sentiment_features['sentiment_negative'] = (sentiment_features['sentiment_mean'] < 0).astype(int)
            sentiment_features['sentiment_neutral'] = (sentiment_features['sentiment_mean'] == 0).astype(int)
            
            # Rolling sentiment features
            for window in [3, 6, 12]:  # hours
                sentiment_features[f'sentiment_mean_ma_{window}'] = sentiment_features['sentiment_mean'].rolling(window).mean()
                sentiment_features[f'sentiment_count_ma_{window}'] = sentiment_features['sentiment_count'].rolling(window).mean()
            
            return sentiment_features
            
        except Exception as e:
            self.logger.error(f"Error aggregating sentiment: {e}")
            return pd.DataFrame()


# Global instances
feature_engineer = FeatureEngineer()
sentiment_engineer = SentimentFeatureEngineer()


def get_feature_engineer() -> FeatureEngineer:
    """Get feature engineer instance."""
    return feature_engineer


def get_sentiment_engineer() -> SentimentFeatureEngineer:
    """Get sentiment engineer instance."""
    return sentiment_engineer


# Utility functions
def create_features_from_quotes(quotes_df: pd.DataFrame, config: FeatureConfig = None) -> pd.DataFrame:
    """Create features from quotes DataFrame."""
    engineer = FeatureEngineer(config)
    return engineer.engineer_features(quotes_df)


def create_sentiment_features(news_df: pd.DataFrame, quotes_df: pd.DataFrame) -> pd.DataFrame:
    """Create sentiment features aligned with quotes."""
    return sentiment_engineer.engineer_sentiment_features(news_df, quotes_df)


def get_feature_importance(features: pd.DataFrame, target: pd.Series) -> Dict[str, float]:
    """Get feature importance scores."""
    return feature_engineer.get_feature_importance(features, target)


# Decorators for automatic feature engineering
def with_feature_engineering(config: FeatureConfig = None):
    """Decorator for automatic feature engineering."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Assume first argument is DataFrame
            if args and isinstance(args[0], pd.DataFrame):
                df = args[0]
                features = create_features_from_quotes(df, config)
                return func(features, *args[1:], **kwargs)
            else:
                return func(*args, **kwargs)
        return wrapper
    return decorator
