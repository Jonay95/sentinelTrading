"""
Backfill strategies for missing data in Sentinel Trading.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from sqlalchemy import text

from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache
from app.infrastructure.metrics import get_metrics
from app.infrastructure.resilience import ResilientAPIManager
from app.container import get_container

logger = logging.getLogger(__name__)


class BackfillStrategy(Enum):
    """Backfill strategy types."""
    FORWARD_FILL = "forward_fill"
    BACKWARD_FILL = "backward_fill"
    LINEAR_INTERPOLATION = "linear_interpolation"
    MEAN_IMPUTATION = "mean_imputation"
    MEDIAN_IMPUTATION = "median_imputation"
    EXTERNAL_API = "external_api"
    HISTORICAL_AVERAGE = "historical_average"
    SEASONAL_IMPUTATION = "seasonal_imputation"


class GapType(Enum):
    """Types of data gaps."""
    MISSING_DAYS = "missing_days"
    MISSING_HOURS = "missing_hours"
    MISSING_VALUES = "missing_values"
    OUTLIERS = "outliers"
    INCONSISTENT_DATA = "inconsistent_data"


@dataclass
class DataGap:
    """Represents a data gap."""
    gap_type: GapType
    start_date: datetime
    end_date: datetime
    asset_id: int
    affected_columns: List[str]
    severity: str  # low, medium, high, critical
    recommended_strategy: BackfillStrategy
    metadata: Dict[str, Any]


@dataclass
class BackfillResult:
    """Result of backfill operation."""
    asset_id: int
    gap_type: GapType
    strategy_used: BackfillStrategy
    records_filled: int
    records_failed: int
    start_time: datetime
    end_time: datetime
    success_rate: float
    metadata: Dict[str, Any]


class GapDetector(LoggerMixin):
    """Detects data gaps in time series data."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.cache = get_cache()
    
    def detect_gaps(self, asset_id: int, start_date: datetime, end_date: datetime) -> List[DataGap]:
        """Detect gaps for an asset within date range."""
        try:
            container = get_container()
            quote_repo = container.quote_repository()
            
            # Get existing data
            quotes = quote_repo.get_by_asset_and_date_range(asset_id, start_date, end_date)
            
            if not quotes:
                return self._create_complete_gap(asset_id, start_date, end_date)
            
            # Convert to DataFrame for analysis
            df = pd.DataFrame([
                {
                    'timestamp': q.timestamp,
                    'open': q.open,
                    'high': q.high,
                    'low': q.low,
                    'close': q.close,
                    'volume': q.volume
                }
                for q in quotes
            ])
            
            gaps = []
            
            # Detect missing dates
            missing_dates_gaps = self._detect_missing_dates(df, asset_id, start_date, end_date)
            gaps.extend(missing_dates_gaps)
            
            # Detect missing values
            missing_values_gaps = self._detect_missing_values(df, asset_id)
            gaps.extend(missing_values_gaps)
            
            # Detect outliers
            outlier_gaps = self._detect_outliers(df, asset_id)
            gaps.extend(outlier_gaps)
            
            # Detect inconsistent data
            inconsistent_gaps = self._detect_inconsistent_data(df, asset_id)
            gaps.extend(inconsistent_gaps)
            
            self.logger.info(f"Detected {len(gaps)} gaps for asset {asset_id}")
            
            return gaps
            
        except Exception as e:
            self.logger.error(f"Error detecting gaps for asset {asset_id}: {e}")
            raise
    
    def _create_complete_gap(self, asset_id: int, start_date: datetime, end_date: datetime) -> List[DataGap]:
        """Create gap when no data exists."""
        return [DataGap(
            gap_type=GapType.MISSING_DAYS,
            start_date=start_date,
            end_date=end_date,
            asset_id=asset_id,
            affected_columns=['open', 'high', 'low', 'close', 'volume'],
            severity="critical",
            recommended_strategy=BackfillStrategy.EXTERNAL_API,
            metadata={"reason": "no_data_found"}
        )]
    
    def _detect_missing_dates(self, df: pd.DataFrame, asset_id: int, start_date: datetime, end_date: datetime) -> List[DataGap]:
        """Detect missing dates in time series."""
        gaps = []
        
        if df.empty:
            return gaps
        
        # Create expected date range
        expected_dates = pd.date_range(start=start_date, end=end_date, freq='D')
        actual_dates = pd.to_datetime(df['timestamp']).dt.date.unique()
        missing_dates = set(expected_dates.date) - set(actual_dates)
        
        if missing_dates:
            # Group consecutive missing dates
            missing_sorted = sorted(missing_dates)
            
            current_gap_start = missing_sorted[0]
            current_gap_end = missing_sorted[0]
            
            for date in missing_sorted[1:]:
                if date == current_gap_end + timedelta(days=1):
                    current_gap_end = date
                else:
                    # Create gap for consecutive dates
                    gaps.append(DataGap(
                        gap_type=GapType.MISSING_DAYS,
                        start_date=datetime.combine(current_gap_start, datetime.min.time()),
                        end_date=datetime.combine(current_gap_end, datetime.min.time()),
                        asset_id=asset_id,
                        affected_columns=['open', 'high', 'low', 'close', 'volume'],
                        severity=self._calculate_gap_severity(len([current_gap_start, current_gap_end])),
                        recommended_strategy=BackfillStrategy.EXTERNAL_API,
                        metadata={"missing_days": list(pd.date_range(current_gap_start, current_gap_end, freq='D'))}
                    ))
                    
                    current_gap_start = date
                    current_gap_end = date
            
            # Add final gap
            gaps.append(DataGap(
                gap_type=GapType.MISSING_DAYS,
                start_date=datetime.combine(current_gap_start, datetime.min.time()),
                end_date=datetime.combine(current_gap_end, datetime.min.time()),
                asset_id=asset_id,
                affected_columns=['open', 'high', 'low', 'close', 'volume'],
                severity=self._calculate_gap_severity(len([current_gap_start, current_gap_end])),
                recommended_strategy=BackfillStrategy.EXTERNAL_API,
                metadata={"missing_days": list(pd.date_range(current_gap_start, current_gap_end, freq='D'))}
            ))
        
        return gaps
    
    def _detect_missing_values(self, df: pd.DataFrame, asset_id: int) -> List[DataGap]:
        """Detect missing values within existing records."""
        gaps = []
        
        if df.empty:
            return gaps
        
        # Check for null values in each column
        for column in ['open', 'high', 'low', 'close', 'volume']:
            null_mask = df[column].isnull()
            
            if null_mask.any():
                null_rows = df[null_mask]
                
                # Group consecutive null rows
                null_indices = null_rows.index.tolist()
                
                if null_indices:
                    gaps.append(DataGap(
                        gap_type=GapType.MISSING_VALUES,
                        start_date=df.loc[null_indices[0], 'timestamp'],
                        end_date=df.loc[null_indices[-1], 'timestamp'],
                        asset_id=asset_id,
                        affected_columns=[column],
                        severity="medium",
                        recommended_strategy=BackfillStrategy.LINEAR_INTERPOLATION,
                        metadata={"null_count": len(null_rows), "rows": null_indices}
                    ))
        
        return gaps
    
    def _detect_outliers(self, df: pd.DataFrame, asset_id: int) -> List[DataGap]:
        """Detect outliers in price and volume data."""
        gaps = []
        
        if df.empty:
            return gaps
        
        # Detect price outliers using IQR method
        for column in ['open', 'high', 'low', 'close']:
            if column in df.columns:
                Q1 = df[column].quantile(0.25)
                Q3 = df[column].quantile(0.75)
                IQR = Q3 - Q1
                
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                outlier_mask = (df[column] < lower_bound) | (df[column] > upper_bound)
                outlier_rows = df[outlier_mask]
                
                if not outlier_rows.empty:
                    gaps.append(DataGap(
                        gap_type=GapType.OUTLIERS,
                        start_date=outlier_rows['timestamp'].min(),
                        end_date=outlier_rows['timestamp'].max(),
                        asset_id=asset_id,
                        affected_columns=[column],
                        severity="medium",
                        recommended_strategy=BackfillStrategy.HISTORICAL_AVERAGE,
                        metadata={
                            "outlier_count": len(outlier_rows),
                            "lower_bound": lower_bound,
                            "upper_bound": upper_bound,
                            "outlier_values": outlier_rows[column].tolist()
                        }
                    ))
        
        # Detect volume outliers
        if 'volume' in df.columns:
            volume_Q1 = df['volume'].quantile(0.25)
            volume_Q3 = df['volume'].quantile(0.75)
            volume_IQR = volume_Q3 - volume_Q1
            
            volume_lower = volume_Q1 - 3 * volume_IQR  # More lenient for volume
            volume_upper = volume_Q3 + 3 * volume_IQR
            
            volume_outliers = df[(df['volume'] < volume_lower) | (df['volume'] > volume_upper)]
            
            if not volume_outliers.empty:
                gaps.append(DataGap(
                    gap_type=GapType.OUTLIERS,
                    start_date=volume_outliers['timestamp'].min(),
                    end_date=volume_outliers['timestamp'].max(),
                    asset_id=asset_id,
                    affected_columns=['volume'],
                    severity="low",  # Volume outliers are less critical
                    recommended_strategy=BackfillStrategy.MEDIAN_IMPUTATION,
                    metadata={
                        "outlier_count": len(volume_outliers),
                        "lower_bound": volume_lower,
                        "upper_bound": volume_upper
                    }
                ))
        
        return gaps
    
    def _detect_inconsistent_data(self, df: pd.DataFrame, asset_id: int) -> List[DataGap]:
        """Detect inconsistent data patterns."""
        gaps = []
        
        if df.empty:
            return gaps
        
        # Check for negative prices
        for column in ['open', 'high', 'low', 'close']:
            if column in df.columns:
                negative_mask = df[column] < 0
                negative_rows = df[negative_mask]
                
                if not negative_rows.empty:
                    gaps.append(DataGap(
                        gap_type=GapType.INCONSISTENT_DATA,
                        start_date=negative_rows['timestamp'].min(),
                        end_date=negative_rows['timestamp'].max(),
                        asset_id=asset_id,
                        affected_columns=[column],
                        severity="high",
                        recommended_strategy=BackfillStrategy.EXTERNAL_API,
                        metadata={"negative_values": negative_rows[column].tolist()}
                    ))
        
        # Check for inconsistent OHLC relationships
        if all(col in df.columns for col in ['open', 'high', 'low', 'close']):
            # High should be >= Open, Low, Close
            ohlc_inconsistent = df[
                (df['high'] < df['open']) |
                (df['high'] < df['low']) |
                (df['high'] < df['close'])
            ]
            
            if not ohlc_inconsistent.empty:
                gaps.append(DataGap(
                    gap_type=GapType.INCONSISTENT_DATA,
                    start_date=ohlc_inconsistent['timestamp'].min(),
                    end_date=ohlc_inconsistent['timestamp'].max(),
                    asset_id=asset_id,
                    affected_columns=['open', 'high', 'low', 'close'],
                    severity="high",
                    recommended_strategy=BackfillStrategy.EXTERNAL_API,
                    metadata={"inconsistent_ohlc_count": len(ohlc_inconsistent)}
                ))
        
        return gaps
    
    def _calculate_gap_severity(self, gap_size: int) -> str:
        """Calculate gap severity based on size."""
        if gap_size >= 30:  # 30+ days
            return "critical"
        elif gap_size >= 7:  # 7-29 days
            return "high"
        elif gap_size >= 3:  # 3-6 days
            return "medium"
        else:  # 1-2 days
            return "low"


class BackfillEngine(LoggerMixin):
    """Engine for backfilling missing data."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.api_manager = ResilientAPIManager()
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    def backfill_gaps(self, gaps: List[DataGap], max_workers: int = 2) -> List[BackfillResult]:
        """Backfill multiple gaps concurrently."""
        results = []
        
        # Group gaps by asset for efficient processing
        gaps_by_asset = {}
        for gap in gaps:
            if gap.asset_id not in gaps_by_asset:
                gaps_by_asset[gap.asset_id] = []
            gaps_by_asset[gap.asset_id].append(gap)
        
        # Process gaps for each asset
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_asset = {
                executor.submit(self._backfill_asset_gaps, asset_id, asset_gaps): asset_id
                for asset_id, asset_gaps in gaps_by_asset.items()
            }
            
            for future in as_completed(future_to_asset):
                asset_id = future_to_asset[future]
                try:
                    asset_results = future.result()
                    results.extend(asset_results)
                except Exception as e:
                    self.logger.error(f"Error backfilling gaps for asset {asset_id}: {e}")
                    
                    # Create failed result
                    failed_result = BackfillResult(
                        asset_id=asset_id,
                        gap_type=GapType.MISSING_DAYS,
                        strategy_used=BackfillStrategy.EXTERNAL_API,
                        records_filled=0,
                        records_failed=len(gaps_by_asset[asset_id]),
                        start_time=datetime.utcnow(),
                        end_time=datetime.utcnow(),
                        success_rate=0.0,
                        metadata={"error": str(e)}
                    )
                    results.append(failed_result)
        
        return results
    
    def _backfill_asset_gaps(self, asset_id: int, gaps: List[DataGap]) -> List[BackfillResult]:
        """Backfill gaps for a single asset."""
        results = []
        
        for gap in gaps:
            try:
                result = self._backfill_single_gap(gap)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Error backfilling gap for asset {asset_id}: {e}")
                
                failed_result = BackfillResult(
                    asset_id=asset_id,
                    gap_type=gap.gap_type,
                    strategy_used=gap.recommended_strategy,
                    records_filled=0,
                    records_failed=1,
                    start_time=datetime.utcnow(),
                    end_time=datetime.utcnow(),
                    success_rate=0.0,
                    metadata={"error": str(e)}
                )
                results.append(failed_result)
        
        return results
    
    def _backfill_single_gap(self, gap: DataGap) -> BackfillResult:
        """Backfill a single data gap."""
        start_time = datetime.utcnow()
        
        try:
            if gap.recommended_strategy == BackfillStrategy.EXTERNAL_API:
                result = self._backfill_with_external_api(gap)
            elif gap.recommended_strategy == BackfillStrategy.LINEAR_INTERPOLATION:
                result = self._backfill_with_interpolation(gap)
            elif gap.recommended_strategy == BackfillStrategy.FORWARD_FILL:
                result = self._backfill_with_forward_fill(gap)
            elif gap.recommended_strategy == BackfillStrategy.MEAN_IMPUTATION:
                result = self._backfill_with_mean_imputation(gap)
            elif gap.recommended_strategy == BackfillStrategy.HISTORICAL_AVERAGE:
                result = self._backfill_with_historical_average(gap)
            else:
                # Default to external API
                result = self._backfill_with_external_api(gap)
            
            result.end_time = datetime.utcnow()
            
            # Record metrics
            self.metrics.record_trading_signal(
                signal_type="backfill_completed",
                asset_symbol=str(gap.asset_id)
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error backfilling gap: {e}")
            
            return BackfillResult(
                asset_id=gap.asset_id,
                gap_type=gap.gap_type,
                strategy_used=gap.recommended_strategy,
                records_filled=0,
                records_failed=1,
                start_time=start_time,
                end_time=datetime.utcnow(),
                success_rate=0.0,
                metadata={"error": str(e)}
            )
    
    def _backfill_with_external_api(self, gap: DataGap) -> BackfillResult:
        """Backfill using external API."""
        container = get_container()
        asset_repo = container.asset_repository()
        quote_repo = container.quote_repository()
        
        # Get asset information
        asset = asset_repo.get_by_id(gap.asset_id)
        if not asset:
            raise ValueError(f"Asset {gap.asset_id} not found")
        
        records_filled = 0
        records_failed = 0
        
        try:
            # Use existing market data ingestion logic
            from app.application.use_cases import IngestMarketDataUseCase
            use_case = IngestMarketDataUseCase(asset_repo, quote_repo, container.config())
            
            # Ingest data for the gap period
            use_case.execute_for_date_range(asset, gap.start_date, gap.end_date)
            
            # Count filled records
            filled_quotes = quote_repo.get_by_asset_and_date_range(
                gap.asset_id, gap.start_date, gap.end_date
            )
            records_filled = len(filled_quotes)
            
        except Exception as e:
            self.logger.error(f"External API backfill failed: {e}")
            records_failed = 1
        
        return BackfillResult(
            asset_id=gap.asset_id,
            gap_type=gap.gap_type,
            strategy_used=BackfillStrategy.EXTERNAL_API,
            records_filled=records_filled,
            records_failed=records_failed,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            success_rate=records_filled / max(records_filled + records_failed, 1),
            metadata={"api_source": asset.provider}
        )
    
    def _backfill_with_interpolation(self, gap: DataGap) -> BackfillResult:
        """Backfill using linear interpolation."""
        # This would require database-level interpolation
        # For now, return placeholder result
        return BackfillResult(
            asset_id=gap.asset_id,
            gap_type=gap.gap_type,
            strategy_used=BackfillStrategy.LINEAR_INTERPOLATION,
            records_filled=0,
            records_failed=0,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            success_rate=0.0,
            metadata={"message": "Interpolation not implemented yet"}
        )
    
    def _backfill_with_forward_fill(self, gap: DataGap) -> BackfillResult:
        """Backfill using forward fill."""
        # This would require database-level forward fill
        # For now, return placeholder result
        return BackfillResult(
            asset_id=gap.asset_id,
            gap_type=gap.gap_type,
            strategy_used=BackfillStrategy.FORWARD_FILL,
            records_filled=0,
            records_failed=0,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            success_rate=0.0,
            metadata={"message": "Forward fill not implemented yet"}
        )
    
    def _backfill_with_mean_imputation(self, gap: DataGap) -> BackfillResult:
        """Backfill using mean imputation."""
        # This would require database-level mean calculation
        # For now, return placeholder result
        return BackfillResult(
            asset_id=gap.asset_id,
            gap_type=gap.gap_type,
            strategy_used=BackfillStrategy.MEAN_IMPUTATION,
            records_filled=0,
            records_failed=0,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            success_rate=0.0,
            metadata={"message": "Mean imputation not implemented yet"}
        )
    
    def _backfill_with_historical_average(self, gap: DataGap) -> BackfillResult:
        """Backfill using historical averages."""
        # This would require historical average calculation
        # For now, return placeholder result
        return BackfillResult(
            asset_id=gap.asset_id,
            gap_type=gap.gap_type,
            strategy_used=BackfillStrategy.HISTORICAL_AVERAGE,
            records_filled=0,
            records_failed=0,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            success_rate=0.0,
            metadata={"message": "Historical average not implemented yet"}
        )


class BackfillManager(LoggerMixin):
    """Manages the complete backfill process."""
    
    def __init__(self):
        self.gap_detector = GapDetector()
        self.backfill_engine = BackfillEngine()
        self.metrics = get_metrics()
        self.cache = get_cache()
    
    def run_backfill_process(self, asset_ids: List[int] = None, days_back: int = 30) -> Dict[str, Any]:
        """Run complete backfill process."""
        try:
            start_time = datetime.utcnow()
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days_back)
            
            # Get assets to process
            if asset_ids is None:
                container = get_container()
                asset_repo = container.asset_repository()
                assets = asset_repo.get_all()
                asset_ids = [asset.id for asset in assets]
            
            self.logger.info(f"Starting backfill process for {len(asset_ids)} assets")
            
            # Detect gaps
            all_gaps = []
            for asset_id in asset_ids:
                try:
                    gaps = self.gap_detector.detect_gaps(asset_id, start_date, end_date)
                    all_gaps.extend(gaps)
                except Exception as e:
                    self.logger.error(f"Error detecting gaps for asset {asset_id}: {e}")
            
            # Backfill gaps
            backfill_results = self.backfill_engine.backfill_gaps(all_gaps)
            
            # Calculate summary statistics
            total_gaps = len(all_gaps)
            total_filled = sum(r.records_filled for r in backfill_results)
            total_failed = sum(r.records_failed for r in backfill_results)
            success_rate = total_filled / max(total_filled + total_failed, 1)
            
            # Group results by gap type
            results_by_type = {}
            for result in backfill_results:
                gap_type = result.gap_type.value
                if gap_type not in results_by_type:
                    results_by_type[gap_type] = {
                        "total_gaps": 0,
                        "records_filled": 0,
                        "records_failed": 0
                    }
                
                results_by_type[gap_type]["total_gaps"] += 1
                results_by_type[gap_type]["records_filled"] += result.records_filled
                results_by_type[gap_type]["records_failed"] += result.records_failed
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            summary = {
                "process_info": {
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "duration_seconds": duration,
                    "assets_processed": len(asset_ids),
                    "date_range": {
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat()
                    }
                },
                "gap_summary": {
                    "total_gaps_detected": total_gaps,
                    "gaps_by_type": {
                        gap_type.value: len([g for g in all_gaps if g.gap_type == gap_type])
                        for gap_type in GapType
                    }
                },
                "backfill_summary": {
                    "total_records_filled": total_filled,
                    "total_records_failed": total_failed,
                    "overall_success_rate": success_rate,
                    "results_by_gap_type": results_by_type
                },
                "detailed_results": [
                    {
                        "asset_id": r.asset_id,
                        "gap_type": r.gap_type.value,
                        "strategy": r.strategy_used.value,
                        "records_filled": r.records_filled,
                        "records_failed": r.records_failed,
                        "success_rate": r.success_rate
                    }
                    for r in backfill_results
                ]
            }
            
            # Cache summary
            cache_key = f"backfill_summary:{datetime.utcnow().strftime('%Y%m%d')}"
            self.cache.set(cache_key, summary, ttl=86400)  # 24 hours TTL
            
            # Record metrics
            self.metrics.record_trading_signal(
                signal_type="backfill_process_completed",
                asset_symbol=f"assets_{len(asset_ids)}"
            )
            
            self.logger.info(f"Backfill process completed: {total_filled} records filled, {total_failed} failed")
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error in backfill process: {e}")
            raise


# Global instances
gap_detector = GapDetector()
backfill_engine = BackfillEngine()
backfill_manager = BackfillManager()


def get_gap_detector() -> GapDetector:
    """Get gap detector instance."""
    return gap_detector


def get_backfill_engine() -> BackfillEngine:
    """Get backfill engine instance."""
    return backfill_engine


def get_backfill_manager() -> BackfillManager:
    """Get backfill manager instance."""
    return backfill_manager


# Utility functions
def detect_and_backfill_asset(asset_id: int, days_back: int = 30) -> Dict[str, Any]:
    """Detect and backfill gaps for a single asset."""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days_back)
    
    # Detect gaps
    gaps = gap_detector.detect_gaps(asset_id, start_date, end_date)
    
    # Backfill gaps
    results = backfill_engine.backfill_gaps(gaps)
    
    return {
        "asset_id": asset_id,
        "gaps_detected": len(gaps),
        "backfill_results": [
            {
                "gap_type": r.gap_type.value,
                "strategy": r.strategy_used.value,
                "records_filled": r.records_filled,
                "success_rate": r.success_rate
            }
            for r in results
        ]
    }


def run_daily_backfill() -> Dict[str, Any]:
    """Run daily backfill process for all assets."""
    return backfill_manager.run_backfill_process(days_back=7)
