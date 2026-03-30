"""
Archive storage for long-term data retention in Sentinel Trading.
"""

import logging
import os
import gzip
import json
import pickle
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import pandas as pd
import numpy as np
from sqlalchemy import text, create_engine
from sqlalchemy.pool import StaticPool
import shutil
from pathlib import Path

from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache
from app.infrastructure.metrics import get_metrics
from app.container import get_container

logger = logging.getLogger(__name__)


class ArchiveFormat(Enum):
    """Archive storage formats."""
    PARQUET = "parquet"
    CSV = "csv"
    JSON = "json"
    PICKLE = "pickle"
    DATABASE = "database"


class CompressionType(Enum):
    """Compression types for archives."""
    GZIP = "gzip"
    SNAPPY = "snappy"
    NONE = "none"


@dataclass
class ArchivePolicy:
    """Archive retention policy."""
    data_type: str
    retention_days: int
    archive_format: ArchiveFormat
    compression: CompressionType
    partition_by: Optional[str] = None  # e.g., 'year', 'month', 'day'
    min_size_mb: int = 100  # Minimum size in MB before archiving


@dataclass
class ArchiveJob:
    """Archive job information."""
    job_id: str
    data_type: str
    start_date: datetime
    end_date: datetime
    records_count: int
    file_size_mb: float
    compression_ratio: float
    archive_path: str
    status: str  # pending, running, completed, failed
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class ArchiveStorage(LoggerMixin):
    """Archive storage manager for long-term data retention."""
    
    def __init__(self, archive_root: str = None):
        self.archive_root = Path(archive_root or os.environ.get('ARCHIVE_ROOT', '/data/archive'))
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.policies = self._initialize_default_policies()
        self._ensure_archive_structure()
    
    def _initialize_default_policies(self) -> Dict[str, ArchivePolicy]:
        """Initialize default archive policies."""
        return {
            'quotes': ArchivePolicy(
                data_type='quotes',
                retention_days=365,  # 1 year
                archive_format=ArchiveFormat.PARQUET,
                compression=CompressionType.GZIP,
                partition_by='month',
                min_size_mb=50
            ),
            'predictions': ArchivePolicy(
                data_type='predictions',
                retention_days=730,  # 2 years
                archive_format=ArchiveFormat.PARQUET,
                compression=CompressionType.GZIP,
                partition_by='quarter',
                min_size_mb=10
            ),
            'news': ArchivePolicy(
                data_type='news',
                retention_days=180,  # 6 months
                archive_format=ArchiveFormat.JSON,
                compression=CompressionType.GZIP,
                partition_by='month',
                min_size_mb=20
            ),
            'prediction_evaluations': ArchivePolicy(
                data_type='prediction_evaluations',
                retention_days=1095,  # 3 years
                archive_format=ArchiveFormat.PARQUET,
                compression=CompressionType.GZIP,
                partition_by='year',
                min_size_mb=5
            )
        }
    
    def _ensure_archive_structure(self):
        """Ensure archive directory structure exists."""
        for data_type in self.policies.keys():
            data_type_dir = self.archive_root / data_type
            data_type_dir.mkdir(parents=True, exist_ok=True)
            
            # Create partition directories
            policy = self.policies[data_type]
            if policy.partition_by:
                if policy.partition_by == 'year':
                    for year in range(2020, datetime.utcnow().year + 2):
                        (data_type_dir / str(year)).mkdir(exist_ok=True)
                elif policy.partition_by == 'quarter':
                    for year in range(2020, datetime.utcnow().year + 2):
                        for quarter in range(1, 5):
                            (data_type_dir / str(year) / f"Q{quarter}").mkdir(exist_ok=True)
                elif policy.partition_by == 'month':
                    for year in range(2020, datetime.utcnow().year + 2):
                        for month in range(1, 13):
                            (data_type_dir / str(year) / f"{month:02d}").mkdir(exist_ok=True)
                elif policy.partition_by == 'day':
                    # Day partitions are created as needed
                    pass
    
    def archive_data(self, data_type: str, cutoff_date: datetime = None) -> ArchiveJob:
        """Archive data of specified type older than cutoff date."""
        try:
            policy = self.policies.get(data_type)
            if not policy:
                raise ValueError(f"No archive policy found for data type: {data_type}")
            
            if cutoff_date is None:
                cutoff_date = datetime.utcnow() - timedelta(days=policy.retention_days)
            
            job_id = f"{data_type}_{cutoff_date.strftime('%Y%m%d_%H%M%S')}"
            
            # Create archive job
            job = ArchiveJob(
                job_id=job_id,
                data_type=data_type,
                start_date=datetime.min,
                end_date=cutoff_date,
                records_count=0,
                file_size_mb=0.0,
                compression_ratio=0.0,
                archive_path="",
                status="pending",
                created_at=datetime.utcnow()
            )
            
            self.logger.info(f"Starting archive job {job_id} for {data_type} data")
            
            # Execute archive job
            if data_type == 'quotes':
                result = self._archive_quotes(job, policy)
            elif data_type == 'predictions':
                result = self._archive_predictions(job, policy)
            elif data_type == 'news':
                result = self._archive_news(job, policy)
            elif data_type == 'prediction_evaluations':
                result = self._archive_evaluations(job, policy)
            else:
                raise ValueError(f"Unsupported data type for archiving: {data_type}")
            
            # Record metrics
            self.metrics.record_trading_signal(
                signal_type="archive_completed",
                asset_symbol=data_type
            )
            
            self.logger.info(f"Archive job {job_id} completed: {result.records_count} records, {result.file_size_mb:.2f} MB")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error archiving {data_type} data: {e}")
            raise
    
    def _archive_quotes(self, job: ArchiveJob, policy: ArchivePolicy) -> ArchiveJob:
        """Archive quotes data."""
        try:
            container = get_container()
            quote_repo = container.quote_repository()
            
            # Get quotes to archive
            quotes = quote_repo.get_older_than(job.end_date)
            
            if not quotes:
                job.status = "completed"
                job.completed_at = datetime.utcnow()
                job.records_count = 0
                return job
            
            # Convert to DataFrame
            df = pd.DataFrame([
                {
                    'id': q.id,
                    'asset_id': q.asset_id,
                    'timestamp': q.timestamp,
                    'open': q.open,
                    'high': q.high,
                    'low': q.low,
                    'close': q.close,
                    'volume': q.volume,
                    'created_at': q.created_at
                }
                for q in quotes
            ])
            
            # Determine archive path
            archive_path = self._get_archive_path(df, policy, 'quotes')
            job.archive_path = str(archive_path)
            
            # Save to archive
            original_size = len(df.to_json()) / 1024 / 1024  # MB
            
            if policy.archive_format == ArchiveFormat.PARQUET:
                if policy.compression == CompressionType.GZIP:
                    df.to_parquet(archive_path, compression='gzip')
                else:
                    df.to_parquet(archive_path)
            elif policy.archive_format == ArchiveFormat.CSV:
                if policy.compression == CompressionType.GZIP:
                    df.to_csv(archive_path, index=False, compression='gzip')
                else:
                    df.to_csv(archive_path, index=False)
            elif policy.archive_format == ArchiveFormat.JSON:
                if policy.compression == CompressionType.GZIP:
                    with gzip.open(archive_path, 'wt') as f:
                        json.dump(df.to_dict('records'), f)
                else:
                    df.to_json(archive_path, orient='records')
            
            # Calculate file size and compression ratio
            file_size_mb = os.path.getsize(archive_path) / 1024 / 1024
            compression_ratio = original_size / file_size_mb if file_size_mb > 0 else 0
            
            # Update job
            job.records_count = len(df)
            job.file_size_mb = file_size_mb
            job.compression_ratio = compression_ratio
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            
            # Remove archived data from database
            quote_repo.delete_older_than(job.end_date)
            
            return job
            
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            raise
    
    def _archive_predictions(self, job: ArchiveJob, policy: ArchivePolicy) -> ArchiveJob:
        """Archive predictions data."""
        try:
            container = get_container()
            prediction_repo = container.prediction_repository()
            
            # Get predictions to archive
            predictions = prediction_repo.get_older_than(job.end_date)
            
            if not predictions:
                job.status = "completed"
                job.completed_at = datetime.utcnow()
                job.records_count = 0
                return job
            
            # Convert to DataFrame
            df = pd.DataFrame([
                {
                    'id': p.id,
                    'asset_id': p.asset_id,
                    'target_date': p.target_date,
                    'signal': p.signal,
                    'confidence': p.confidence,
                    'target_price': p.target_price,
                    'time_horizon': p.time_horizon,
                    'model_version': p.model_version,
                    'created_at': p.created_at
                }
                for p in predictions
            ])
            
            # Determine archive path
            archive_path = self._get_archive_path(df, policy, 'predictions')
            job.archive_path = str(archive_path)
            
            # Save to archive
            if policy.archive_format == ArchiveFormat.PARQUET:
                if policy.compression == CompressionType.GZIP:
                    df.to_parquet(archive_path, compression='gzip')
                else:
                    df.to_parquet(archive_path)
            
            # Calculate file size
            file_size_mb = os.path.getsize(archive_path) / 1024 / 1024
            
            # Update job
            job.records_count = len(df)
            job.file_size_mb = file_size_mb
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            
            # Remove archived data from database
            prediction_repo.delete_older_than(job.end_date)
            
            return job
            
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            raise
    
    def _archive_news(self, job: ArchiveJob, policy: ArchivePolicy) -> ArchiveJob:
        """Archive news data."""
        try:
            container = get_container()
            news_repo = container.news_read_repository()
            
            # Get news to archive
            news = news_repo.get_older_than(job.end_date)
            
            if not news:
                job.status = "completed"
                job.completed_at = datetime.utcnow()
                job.records_count = 0
                return job
            
            # Convert to DataFrame
            df = pd.DataFrame([
                {
                    'id': n.id,
                    'title': n.title,
                    'content': n.content,
                    'source': n.source,
                    'url': n.url,
                    'published_at': n.published_at,
                    'sentiment': n.sentiment,
                    'keywords': n.keywords,
                    'asset_symbols': n.asset_symbols,
                    'created_at': n.created_at
                }
                for n in news
            ])
            
            # Determine archive path
            archive_path = self._get_archive_path(df, policy, 'news')
            job.archive_path = str(archive_path)
            
            # Save to archive
            if policy.archive_format == ArchiveFormat.JSON:
                if policy.compression == CompressionType.GZIP:
                    with gzip.open(archive_path, 'wt') as f:
                        json.dump(df.to_dict('records'), f)
                else:
                    df.to_json(archive_path, orient='records')
            
            # Calculate file size
            file_size_mb = os.path.getsize(archive_path) / 1024 / 1024
            
            # Update job
            job.records_count = len(df)
            job.file_size_mb = file_size_mb
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            
            # Remove archived data from database
            news_repo.delete_older_than(job.end_date)
            
            return job
            
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            raise
    
    def _archive_evaluations(self, job: ArchiveJob, policy: ArchivePolicy) -> ArchiveJob:
        """Archive prediction evaluation data."""
        try:
            container = get_container()
            eval_repo = container.prediction_evaluation_repository()
            
            # Get evaluations to archive
            evaluations = eval_repo.get_older_than(job.end_date)
            
            if not evaluations:
                job.status = "completed"
                job.completed_at = datetime.utcnow()
                job.records_count = 0
                return job
            
            # Convert to DataFrame
            df = pd.DataFrame([
                {
                    'id': e.id,
                    'prediction_id': e.prediction_id,
                    'actual_signal': e.actual_signal,
                    'actual_price': e.actual_price,
                    'accuracy': e.accuracy,
                    'price_error': e.price_error,
                    'evaluated_at': e.evaluated_at,
                    'created_at': e.created_at
                }
                for e in evaluations
            ])
            
            # Determine archive path
            archive_path = self._get_archive_path(df, policy, 'prediction_evaluations')
            job.archive_path = str(archive_path)
            
            # Save to archive
            if policy.archive_format == ArchiveFormat.PARQUET:
                if policy.compression == CompressionType.GZIP:
                    df.to_parquet(archive_path, compression='gzip')
                else:
                    df.to_parquet(archive_path)
            
            # Calculate file size
            file_size_mb = os.path.getsize(archive_path) / 1024 / 1024
            
            # Update job
            job.records_count = len(df)
            job.file_size_mb = file_size_mb
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            
            # Remove archived data from database
            eval_repo.delete_older_than(job.end_date)
            
            return job
            
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            raise
    
    def _get_archive_path(self, df: pd.DataFrame, policy: ArchivePolicy, data_type: str) -> Path:
        """Get archive path based on policy and data."""
        base_dir = self.archive_root / data_type
        
        if policy.partition_by and not df.empty:
            # Get date column for partitioning
            date_col = 'timestamp' if 'timestamp' in df.columns else 'created_at'
            if date_col in df.columns:
                dates = pd.to_datetime(df[date_col])
                
                if policy.partition_by == 'year':
                    year = dates.min().year
                    return base_dir / str(year) / f"{data_type}_{year}.parquet"
                elif policy.partition_by == 'quarter':
                    year = dates.min().year
                    quarter = (dates.min().month - 1) // 3 + 1
                    return base_dir / str(year) / f"Q{quarter}" / f"{data_type}_{year}_Q{quarter}.parquet"
                elif policy.partition_by == 'month':
                    year = dates.min().year
                    month = dates.min().month
                    return base_dir / str(year) / f"{month:02d}" / f"{data_type}_{year}_{month:02d}.parquet"
                elif policy.partition_by == 'day':
                    year = dates.min().year
                    month = dates.min().month
                    day = dates.min().day
                    return base_dir / str(year) / f"{month:02d}" / f"{day:02d}" / f"{data_type}_{year}_{month:02d}_{day:02d}.parquet"
        
        # Default path
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"{data_type}_{timestamp}.parquet"
        return base_dir / filename
    
    def restore_data(self, data_type: str, start_date: datetime, end_date: datetime) -> bool:
        """Restore archived data back to database."""
        try:
            policy = self.policies.get(data_type)
            if not policy:
                raise ValueError(f"No archive policy found for data type: {data_type}")
            
            # Find archive files for date range
            archive_files = self._find_archive_files(data_type, start_date, end_date)
            
            if not archive_files:
                self.logger.info(f"No archive files found for {data_type} in date range")
                return True
            
            self.logger.info(f"Found {len(archive_files)} archive files to restore")
            
            # Restore each file
            for file_path in archive_files:
                self._restore_archive_file(file_path, data_type)
            
            self.logger.info(f"Successfully restored {data_type} data from {len(archive_files)} archive files")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error restoring {data_type} data: {e}")
            return False
    
    def _find_archive_files(self, data_type: str, start_date: datetime, end_date: datetime) -> List[Path]:
        """Find archive files for date range."""
        files = []
        base_dir = self.archive_root / data_type
        
        if not base_dir.exists():
            return files
        
        # Walk through archive directory
        for file_path in base_dir.rglob(f"*.{policy.archive_format.value}"):
            try:
                # Extract date from filename
                date_from_filename = self._extract_date_from_filename(file_path.name, data_type)
                
                if date_from_filename and start_date <= date_from_filename <= end_date:
                    files.append(file_path)
            except Exception:
                continue
        
        return sorted(files)
    
    def _extract_date_from_filename(self, filename: str, data_type: str) -> Optional[datetime]:
        """Extract date from archive filename."""
        try:
            # Expected format: data_type_YYYY_MM_DD.parquet or data_type_YYYY.parquet
            parts = filename.replace(f'{data_type}_', '').replace('.parquet', '').replace('.csv', '').replace('.json', '').split('_')
            
            if len(parts) >= 3:
                # YYYY_MM_DD format
                year, month, day = map(int, parts[:3])
                return datetime(year, month, day)
            elif len(parts) == 1 and len(parts[0]) == 4:
                # YYYY format
                year = int(parts[0])
                return datetime(year, 1, 1)
            
        except Exception:
            pass
        
        return None
    
    def _restore_archive_file(self, file_path: Path, data_type: str):
        """Restore data from archive file."""
        try:
            # Read archive file
            if file_path.suffix == '.parquet':
                df = pd.read_parquet(file_path)
            elif file_path.suffix == '.csv':
                df = pd.read_csv(file_path)
            elif file_path.suffix == '.json':
                df = pd.read_json(file_path)
            else:
                raise ValueError(f"Unsupported archive format: {file_path.suffix}")
            
            # Restore to database based on data type
            if data_type == 'quotes':
                self._restore_quotes_to_db(df)
            elif data_type == 'predictions':
                self._restore_predictions_to_db(df)
            elif data_type == 'news':
                self._restore_news_to_db(df)
            elif data_type == 'prediction_evaluations':
                self._restore_evaluations_to_db(df)
            
        except Exception as e:
            self.logger.error(f"Error restoring archive file {file_path}: {e}")
            raise
    
    def _restore_quotes_to_db(self, df: pd.DataFrame):
        """Restore quotes to database."""
        # This would implement bulk insert of quotes back to database
        # For now, just log the operation
        self.logger.info(f"Restoring {len(df)} quotes to database")
    
    def _restore_predictions_to_db(self, df: pd.DataFrame):
        """Restore predictions to database."""
        self.logger.info(f"Restoring {len(df)} predictions to database")
    
    def _restore_news_to_db(self, df: pd.DataFrame):
        """Restore news to database."""
        self.logger.info(f"Restoring {len(df)} news articles to database")
    
    def _restore_evaluations_to_db(self, df: pd.DataFrame):
        """Restore evaluations to database."""
        self.logger.info(f"Restoring {len(df)} evaluations to database")
    
    def get_archive_stats(self) -> Dict[str, Any]:
        """Get archive storage statistics."""
        try:
            stats = {
                "archive_root": str(self.archive_root),
                "total_size_mb": 0,
                "file_count": 0,
                "data_types": {}
            }
            
            # Calculate total size and file count
            for data_type in self.policies.keys():
                data_type_dir = self.archive_root / data_type
                
                if data_type_dir.exists():
                    type_stats = {
                        "size_mb": 0,
                        "file_count": 0,
                        "latest_archive": None
                    }
                    
                    for file_path in data_type_dir.rglob("*"):
                        if file_path.is_file():
                            size_mb = file_path.stat().st_size / 1024 / 1024
                            type_stats["size_mb"] += size_mb
                            type_stats["file_count"] += 1
                            
                            if type_stats["latest_archive"] is None or file_path.stat().st_mtime > type_stats["latest_archive"].stat().st_mtime:
                                type_stats["latest_archive"] = file_path
                    
                    stats["total_size_mb"] += type_stats["size_mb"]
                    stats["file_count"] += type_stats["file_count"]
                    stats["data_types"][data_type] = type_stats
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting archive stats: {e}")
            return {"error": str(e)}


class ArchiveManager(LoggerMixin):
    """Manager for archive operations and scheduling."""
    
    def __init__(self, archive_storage: ArchiveStorage = None):
        self.archive_storage = archive_storage or ArchiveStorage()
        self.metrics = get_metrics()
        self.cache = get_cache()
    
    def run_archive_cleanup(self) -> Dict[str, Any]:
        """Run archive cleanup for all data types."""
        try:
            start_time = datetime.utcnow()
            results = {}
            
            for data_type, policy in self.archive_storage.policies.items():
                try:
                    self.logger.info(f"Starting archive cleanup for {data_type}")
                    
                    job = self.archive_storage.archive_data(data_type)
                    
                    results[data_type] = {
                        "job_id": job.job_id,
                        "status": job.status,
                        "records_count": job.records_count,
                        "file_size_mb": job.file_size_mb,
                        "compression_ratio": job.compression_ratio,
                        "error": job.error_message
                    }
                    
                    if job.status == "completed":
                        self.logger.info(f"Archive cleanup for {data_type} completed: {job.records_count} records archived")
                    else:
                        self.logger.error(f"Archive cleanup for {data_type} failed: {job.error_message}")
                
                except Exception as e:
                    self.logger.error(f"Error in archive cleanup for {data_type}: {e}")
                    results[data_type] = {
                        "error": str(e),
                        "status": "failed"
                    }
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            summary = {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "results": results,
                "archive_stats": self.archive_storage.get_archive_stats()
            }
            
            # Cache summary
            cache_key = f"archive_cleanup_summary:{datetime.utcnow().strftime('%Y%m%d')}"
            self.cache.set(cache_key, summary, ttl=86400)  # 24 hours TTL
            
            # Record metrics
            self.metrics.record_trading_signal(
                signal_type="archive_cleanup_completed",
                asset_symbol="all_data_types"
            )
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error in archive cleanup: {e}")
            raise
    
    def schedule_archive_jobs(self) -> List[str]:
        """Schedule archive jobs based on policies."""
        scheduled_jobs = []
        
        for data_type, policy in self.archive_storage.policies.items():
            try:
                # Check if archiving is needed
                cutoff_date = datetime.utcnow() - timedelta(days=policy.retention_days)
                
                # Create job ID
                job_id = f"scheduled_{data_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                
                # In a real implementation, this would schedule background jobs
                # For now, just return the job IDs
                scheduled_jobs.append(job_id)
                
                self.logger.info(f"Scheduled archive job {job_id} for {data_type}")
                
            except Exception as e:
                self.logger.error(f"Error scheduling archive job for {data_type}: {e}")
        
        return scheduled_jobs


# Global instances
archive_storage = ArchiveStorage()
archive_manager = ArchiveManager()


def get_archive_storage() -> ArchiveStorage:
    """Get archive storage instance."""
    return archive_storage


def get_archive_manager() -> ArchiveManager:
    """Get archive manager instance."""
    return archive_manager


# Utility functions
def archive_data_type(data_type: str, cutoff_date: datetime = None) -> ArchiveJob:
    """Archive specific data type."""
    return archive_storage.archive_data(data_type, cutoff_date)


def restore_data_type(data_type: str, start_date: datetime, end_date: datetime) -> bool:
    """Restore specific data type."""
    return archive_storage.restore_data(data_type, start_date, end_date)


def run_daily_archive_cleanup() -> Dict[str, Any]:
    """Run daily archive cleanup."""
    return archive_manager.run_archive_cleanup()


def get_archive_statistics() -> Dict[str, Any]:
    """Get archive storage statistics."""
    return archive_storage.get_archive_stats()
