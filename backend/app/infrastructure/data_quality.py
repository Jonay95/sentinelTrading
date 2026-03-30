"""
Data quality validation and monitoring for Sentinel Trading.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np
from great_expectations.dataset import PandasDataset
from great_expectations.core.expectation_suite import ExpectationSuite
from great_expectations.core.expectation_configuration import ExpectationConfiguration
import great_expectations as ge

from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache
from app.infrastructure.metrics import get_metrics

logger = logging.getLogger(__name__)


class QualityLevel(Enum):
    """Data quality levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


@dataclass
class QualityIssue:
    """Data quality issue."""
    issue_type: str
    severity: str
    description: str
    affected_records: int
    affected_columns: List[str]
    recommendation: str
    timestamp: datetime


@dataclass
class QualityReport:
    """Data quality report."""
    dataset_name: str
    quality_level: QualityLevel
    total_records: int
    issues: List[QualityIssue]
    score: float  # 0-100
    validation_time: datetime
    metadata: Dict[str, Any]


class DataQualityValidator(LoggerMixin):
    """Data quality validator using Great Expectations."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.suites = {}
        self._initialize_default_suites()
    
    def _initialize_default_suites(self):
        """Initialize default expectation suites."""
        
        # Market data suite
        market_data_suite = ExpectationSuite(
            expectation_suite_name="market_data_suite"
        )
        
        market_data_suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_table_row_count_to_be_between",
                kwargs={"min_value": 1, "max_value": 1000000}
            )
        )
        
        market_data_suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_column_values_to_not_be_null",
                kwargs={"column": "timestamp"}
            )
        )
        
        market_data_suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_column_values_to_be_between",
                kwargs={"column": "price", "min_value": 0, "max_value": 1000000}
            )
        )
        
        market_data_suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_column_values_to_be_between",
                kwargs={"column": "volume", "min_value": 0, "max_value": 10000000000}
            )
        )
        
        market_data_suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_column_values_to_be_unique",
                kwargs={"column": ["timestamp", "asset_id"]}
            )
        )
        
        self.suites["market_data"] = market_data_suite
        
        # Predictions suite
        predictions_suite = ExpectationSuite(
            expectation_suite_name="predictions_suite"
        )
        
        predictions_suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_table_row_count_to_be_between",
                kwargs={"min_value": 0, "max_value": 100000}
            )
        )
        
        predictions_suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_column_values_to_not_be_null",
                kwargs={"column": "target_date"}
            )
        )
        
        predictions_suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_column_values_to_be_in_set",
                kwargs={"column": "signal", "value_set": ["BUY", "SELL", "HOLD"]}
            )
        )
        
        predictions_suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_column_values_to_be_between",
                kwargs={"column": "confidence", "min_value": 0, "max_value": 1}
            )
        )
        
        self.suites["predictions"] = predictions_suite
        
        # News suite
        news_suite = ExpectationSuite(
            expectation_suite_name="news_suite"
        )
        
        news_suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_table_row_count_to_be_between",
                kwargs={"min_value": 0, "max_value": 10000}
            )
        )
        
        news_suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_column_values_to_not_be_null",
                kwargs={"column": "title"}
            )
        )
        
        news_suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_column_values_to_not_be_null",
                kwargs={"column": "published_at"}
            )
        )
        
        news_suite.add_expectation(
            ExpectationConfiguration(
                expectation_type="expect_column_values_to_be_between",
                kwargs={"column": "sentiment", "min_value": -1, "max_value": 1}
            )
        )
        
        self.suites["news"] = news_suite
    
    def validate_market_data(self, df: pd.DataFrame, dataset_name: str = "market_data") -> QualityReport:
        """Validate market data quality."""
        try:
            # Convert to Great Expectations dataset
            ge_df = ge.from_pandas(df)
            
            # Get appropriate suite
            suite = self.suites.get("market_data")
            if not suite:
                raise ValueError("Market data suite not found")
            
            # Run validation
            results = ge_df.validate(suite, result_format="SUMMARY")
            
            # Analyze results
            issues = self._analyze_validation_results(results, "market_data")
            score = self._calculate_quality_score(results)
            quality_level = self._determine_quality_level(score)
            
            report = QualityReport(
                dataset_name=dataset_name,
                quality_level=quality_level,
                total_records=len(df),
                issues=issues,
                score=score,
                validation_time=datetime.utcnow(),
                metadata={
                    "validation_results": results.to_json_dict(),
                    "suite_name": "market_data_suite"
                }
            )
            
            # Cache report
            cache_key = f"quality_report:{dataset_name}"
            self.cache.set(cache_key, report.__dict__, ttl=3600)  # 1 hour TTL
            
            # Record metrics
            self.metrics.record_error("data_quality_issue", f"market_data_{quality_level.value}")
            
            self.logger.info(f"Market data quality validation completed: {quality_level.value} ({score:.1f}/100)")
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error validating market data: {e}")
            raise
    
    def validate_predictions(self, df: pd.DataFrame, dataset_name: str = "predictions") -> QualityReport:
        """Validate predictions data quality."""
        try:
            ge_df = ge.from_pandas(df)
            suite = self.suites.get("predictions")
            
            if not suite:
                raise ValueError("Predictions suite not found")
            
            results = ge_df.validate(suite, result_format="SUMMARY")
            
            issues = self._analyze_validation_results(results, "predictions")
            score = self._calculate_quality_score(results)
            quality_level = self._determine_quality_level(score)
            
            report = QualityReport(
                dataset_name=dataset_name,
                quality_level=quality_level,
                total_records=len(df),
                issues=issues,
                score=score,
                validation_time=datetime.utcnow(),
                metadata={
                    "validation_results": results.to_json_dict(),
                    "suite_name": "predictions_suite"
                }
            )
            
            # Cache report
            cache_key = f"quality_report:{dataset_name}"
            self.cache.set(cache_key, report.__dict__, ttl=3600)
            
            self.metrics.record_error("data_quality_issue", f"predictions_{quality_level.value}")
            
            self.logger.info(f"Predictions data quality validation completed: {quality_level.value} ({score:.1f}/100)")
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error validating predictions: {e}")
            raise
    
    def validate_news(self, df: pd.DataFrame, dataset_name: str = "news") -> QualityReport:
        """Validate news data quality."""
        try:
            ge_df = ge.from_pandas(df)
            suite = self.suites.get("news")
            
            if not suite:
                raise ValueError("News suite not found")
            
            results = ge_df.validate(suite, result_format="SUMMARY")
            
            issues = self._analyze_validation_results(results, "news")
            score = self._calculate_quality_score(results)
            quality_level = self._determine_quality_level(score)
            
            report = QualityReport(
                dataset_name=dataset_name,
                quality_level=quality_level,
                total_records=len(df),
                issues=issues,
                score=score,
                validation_time=datetime.utcnow(),
                metadata={
                    "validation_results": results.to_json_dict(),
                    "suite_name": "news_suite"
                }
            )
            
            # Cache report
            cache_key = f"quality_report:{dataset_name}"
            self.cache.set(cache_key, report.__dict__, ttl=3600)
            
            self.metrics.record_error("data_quality_issue", f"news_{quality_level.value}")
            
            self.logger.info(f"News data quality validation completed: {quality_level.value} ({score:.1f}/100)")
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error validating news: {e}")
            raise
    
    def _analyze_validation_results(self, results, dataset_type: str) -> List[QualityIssue]:
        """Analyze validation results and create quality issues."""
        issues = []
        
        for result in results.results:
            if not result.success:
                severity = self._determine_issue_severity(result.expectation_config.expectation_type)
                
                issue = QualityIssue(
                    issue_type=result.expectation_config.expectation_type,
                    severity=severity,
                    description=result.exception_info["raised_exception_message"],
                    affected_records=result.result["unexpected_count"],
                    affected_columns=result.expectation_config.kwargs.get("column", []),
                    recommendation=self._get_recommendation(result.expectation_config.expectation_type),
                    timestamp=datetime.utcnow()
                )
                
                issues.append(issue)
        
        return issues
    
    def _calculate_quality_score(self, results) -> float:
        """Calculate overall quality score (0-100)."""
        if not results.results:
            return 0.0
        
        total_expectations = len(results.results)
        successful_expectations = sum(1 for result in results.results if result.success)
        
        base_score = (successful_expectations / total_expectations) * 100
        
        # Apply penalties for failed expectations
        penalty = 0
        for result in results.results:
            if not result.success:
                # More severe expectations get higher penalties
                if "null" in result.expectation_config.expectation_type.lower():
                    penalty += 5
                elif "unique" in result.expectation_config.expectation_type.lower():
                    penalty += 3
                else:
                    penalty += 2
        
        return max(0, base_score - penalty)
    
    def _determine_quality_level(self, score: float) -> QualityLevel:
        """Determine quality level based on score."""
        if score >= 90:
            return QualityLevel.EXCELLENT
        elif score >= 80:
            return QualityLevel.GOOD
        elif score >= 70:
            return QualityLevel.FAIR
        elif score >= 50:
            return QualityLevel.POOR
        else:
            return QualityLevel.CRITICAL
    
    def _determine_issue_severity(self, expectation_type: str) -> str:
        """Determine severity of quality issue."""
        if "null" in expectation_type.lower():
            return "high"
        elif "unique" in expectation_type.lower():
            return "medium"
        elif "between" in expectation_type.lower():
            return "medium"
        else:
            return "low"
    
    def _get_recommendation(self, expectation_type: str) -> str:
        """Get recommendation for quality issue."""
        recommendations = {
            "expect_column_values_to_not_be_null": "Check data source for missing values and implement data cleaning",
            "expect_column_values_to_be_unique": "Check for duplicate records and implement deduplication",
            "expect_column_values_to_be_between": "Validate data range and implement outlier detection",
            "expect_table_row_count_to_be_between": "Check data ingestion process and expected data volume",
            "expect_column_values_to_be_in_set": "Validate allowed values and implement data validation",
        }
        
        return recommendations.get(expectation_type, "Review data quality and implement appropriate validation")


class DataProfiler(LoggerMixin):
    """Data profiler for generating data profiles and statistics."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.cache = get_cache()
    
    def profile_market_data(self, df: pd.DataFrame, asset_symbol: str = None) -> Dict[str, Any]:
        """Generate profile for market data."""
        try:
            profile = {
                "dataset_type": "market_data",
                "asset_symbol": asset_symbol,
                "timestamp": datetime.utcnow().isoformat(),
                "basic_stats": self._get_basic_stats(df),
                "price_analysis": self._analyze_prices(df),
                "volume_analysis": self._analyze_volumes(df),
                "time_analysis": self._analyze_time_series(df),
                "data_quality": self._assess_data_quality(df)
            }
            
            # Cache profile
            cache_key = f"profile:market_data:{asset_symbol or 'all'}"
            self.cache.set(cache_key, profile, ttl=3600)
            
            return profile
            
        except Exception as e:
            self.logger.error(f"Error profiling market data: {e}")
            raise
    
    def profile_predictions(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate profile for predictions."""
        try:
            profile = {
                "dataset_type": "predictions",
                "timestamp": datetime.utcnow().isoformat(),
                "basic_stats": self._get_basic_stats(df),
                "prediction_analysis": self._analyze_predictions(df),
                "confidence_analysis": self._analyze_confidence(df),
                "accuracy_analysis": self._analyze_accuracy(df),
                "data_quality": self._assess_data_quality(df)
            }
            
            # Cache profile
            cache_key = "profile:predictions"
            self.cache.set(cache_key, profile, ttl=3600)
            
            return profile
            
        except Exception as e:
            self.logger.error(f"Error profiling predictions: {e}")
            raise
    
    def _get_basic_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get basic dataset statistics."""
        return {
            "total_records": len(df),
            "total_columns": len(df.columns),
            "memory_usage_mb": df.memory_usage(deep=True).sum() / 1024 / 1024,
            "null_counts": df.isnull().sum().to_dict(),
            "duplicate_rows": df.duplicated().sum(),
            "data_types": df.dtypes.to_dict()
        }
    
    def _analyze_prices(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze price data."""
        if 'price' not in df.columns:
            return {}
        
        prices = df['price'].dropna()
        
        return {
            "min_price": float(prices.min()),
            "max_price": float(prices.max()),
            "mean_price": float(prices.mean()),
            "median_price": float(prices.median()),
            "std_price": float(prices.std()),
            "price_volatility": float(prices.std() / prices.mean() * 100),
            "price_trend": self._calculate_trend(prices),
            "outliers": self._detect_outliers(prices)
        }
    
    def _analyze_volumes(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze volume data."""
        if 'volume' not in df.columns:
            return {}
        
        volumes = df['volume'].dropna()
        
        return {
            "min_volume": float(volumes.min()),
            "max_volume": float(volumes.max()),
            "mean_volume": float(volumes.mean()),
            "median_volume": float(volumes.median()),
            "std_volume": float(volumes.std()),
            "zero_volume_days": int((volumes == 0).sum()),
            "high_volume_days": int((volumes > volumes.quantile(0.9)).sum())
        }
    
    def _analyze_time_series(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze time series properties."""
        if 'timestamp' not in df.columns:
            return {}
        
        timestamps = pd.to_datetime(df['timestamp'])
        
        return {
            "date_range": {
                "start": timestamps.min().isoformat(),
                "end": timestamps.max().isoformat()
            },
            "total_days": (timestamps.max() - timestamps.min()).days,
            "gaps_detected": self._detect_time_gaps(timestamps),
            "frequency": self._detect_frequency(timestamps),
            "weekend_data": self._check_weekend_data(timestamps)
        }
    
    def _analyze_predictions(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze prediction distribution."""
        if 'signal' not in df.columns:
            return {}
        
        signals = df['signal'].value_counts()
        
        return {
            "signal_distribution": signals.to_dict(),
            "buy_percentage": float(signals.get('BUY', 0) / len(df) * 100),
            "sell_percentage": float(signals.get('SELL', 0) / len(df) * 100),
            "hold_percentage": float(signals.get('HOLD', 0) / len(df) * 100),
            "prediction_frequency": len(df) / df['target_date'].nunique() if 'target_date' in df.columns else 0
        }
    
    def _analyze_confidence(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze confidence scores."""
        if 'confidence' not in df.columns:
            return {}
        
        confidence = df['confidence'].dropna()
        
        return {
            "mean_confidence": float(confidence.mean()),
            "median_confidence": float(confidence.median()),
            "std_confidence": float(confidence.std()),
            "high_confidence_ratio": float((confidence >= 0.8).sum() / len(confidence)),
            "low_confidence_ratio": float((confidence < 0.5).sum() / len(confidence))
        }
    
    def _analyze_accuracy(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze prediction accuracy if available."""
        if 'actual_signal' not in df.columns or 'signal' not in df.columns:
            return {}
        
        accuracy = (df['signal'] == df['actual_signal']).mean()
        
        return {
            "overall_accuracy": float(accuracy),
            "signal_accuracy": df.groupby('signal').apply(
                lambda x: (x['signal'] == x['actual_signal']).mean()
            ).to_dict()
        }
    
    def _assess_data_quality(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Assess basic data quality."""
        return {
            "completeness": float((1 - df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100),
            "uniqueness": float((1 - df.duplicated().sum() / len(df)) * 100),
            "consistency": self._check_consistency(df),
            "validity": self._check_validity(df)
        }
    
    def _calculate_trend(self, series: pd.Series) -> str:
        """Calculate trend direction."""
        if len(series) < 2:
            return "insufficient_data"
        
        # Simple linear regression
        x = np.arange(len(series))
        slope = np.polyfit(x, series, 1)[0]
        
        if slope > 0.01:
            return "upward"
        elif slope < -0.01:
            return "downward"
        else:
            return "stable"
    
    def _detect_outliers(self, series: pd.Series) -> Dict[str, Any]:
        """Detect outliers using IQR method."""
        Q1 = series.quantile(0.25)
        Q3 = series.quantile(0.75)
        IQR = Q3 - Q1
        
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        outliers = series[(series < lower_bound) | (series > upper_bound)]
        
        return {
            "count": len(outliers),
            "percentage": float(len(outliers) / len(series) * 100),
            "lower_bound": float(lower_bound),
            "upper_bound": float(upper_bound)
        }
    
    def _detect_time_gaps(self, timestamps: pd.Series) -> List[str]:
        """Detect gaps in time series."""
        if len(timestamps) < 2:
            return []
        
        # Sort timestamps
        sorted_ts = timestamps.sort_values()
        
        # Calculate differences
        time_diffs = sorted_ts.diff().dropna()
        
        # Find gaps larger than expected (assuming daily data)
        expected_diff = pd.Timedelta(days=1)
        gaps = time_diffs[time_diffs > expected_diff]
        
        return [f"Gap of {gap.days} days detected" for gap in gaps]
    
    def _detect_frequency(self, timestamps: pd.Series) -> str:
        """Detect data frequency."""
        if len(timestamps) < 2:
            return "insufficient_data"
        
        # Calculate most common difference
        time_diffs = timestamps.sort_values().diff().dropna()
        most_common_diff = time_diffs.mode().iloc[0] if not time_diffs.mode().empty else pd.Timedelta(days=1)
        
        if most_common_diff <= pd.Timedelta(hours=1):
            return "intraday"
        elif most_common_diff <= pd.Timedelta(days=1):
            return "daily"
        elif most_common_diff <= pd.Timedelta(days=7):
            return "weekly"
        else:
            return "monthly"
    
    def _check_weekend_data(self, timestamps: pd.Series) -> Dict[str, Any]:
        """Check for weekend data."""
        weekend_data = timestamps.dt.dayofweek >= 5
        
        return {
            "has_weekend_data": bool(weekend_data.any()),
            "weekend_records": int(weekend_data.sum()),
            "weekend_percentage": float(weekend_data.sum() / len(timestamps) * 100)
        }
    
    def _check_consistency(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Check data consistency."""
        issues = []
        
        # Check for negative prices or volumes
        if 'price' in df.columns:
            negative_prices = (df['price'] < 0).sum()
            if negative_prices > 0:
                issues.append(f"Found {negative_prices} negative prices")
        
        if 'volume' in df.columns:
            negative_volumes = (df['volume'] < 0).sum()
            if negative_volumes > 0:
                issues.append(f"Found {negative_volumes} negative volumes")
        
        return {
            "issues": issues,
            "consistency_score": max(0, 100 - len(issues) * 10)
        }
    
    def _check_validity(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Check data validity."""
        issues = []
        
        # Check for extreme values
        if 'price' in df.columns:
            extreme_prices = (df['price'] > 1000000) | (df['price'] < 0.001)
            if extreme_prices.any():
                issues.append(f"Found {extreme_prices.sum()} extreme price values")
        
        if 'confidence' in df.columns:
            invalid_confidence = (df['confidence'] < 0) | (df['confidence'] > 1)
            if invalid_confidence.any():
                issues.append(f"Found {invalid_confidence.sum()} invalid confidence values")
        
        return {
            "issues": issues,
            "validity_score": max(0, 100 - len(issues) * 10)
        }


# Global instances
data_validator = DataQualityValidator()
data_profiler = DataProfiler()


def get_data_validator() -> DataQualityValidator:
    """Get data validator instance."""
    return data_validator


def get_data_profiler() -> DataProfiler:
    """Get data profiler instance."""
    return data_profiler


# Utility functions
def validate_dataset(df: pd.DataFrame, dataset_type: str, dataset_name: str = None) -> QualityReport:
    """Validate dataset based on type."""
    if dataset_type == "market_data":
        return data_validator.validate_market_data(df, dataset_name or "market_data")
    elif dataset_type == "predictions":
        return data_validator.validate_predictions(df, dataset_name or "predictions")
    elif dataset_type == "news":
        return data_validator.validate_news(df, dataset_name or "news")
    else:
        raise ValueError(f"Unknown dataset type: {dataset_type}")


def profile_dataset(df: pd.DataFrame, dataset_type: str, **kwargs) -> Dict[str, Any]:
    """Profile dataset based on type."""
    if dataset_type == "market_data":
        return data_profiler.profile_market_data(df, **kwargs)
    elif dataset_type == "predictions":
        return data_profiler.profile_predictions(df)
    else:
        raise ValueError(f"Unknown dataset type: {dataset_type}")
