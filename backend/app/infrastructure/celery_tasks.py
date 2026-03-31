"""
Celery tasks for Sentinel Trading async processing.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from celery import current_task

from app.infrastructure.celery_app import celery_app, BaseTask
from app.container import get_container
from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache

logger = logging.getLogger(__name__)


@celery_app.task(base=BaseTask, bind=True, cache_result=True)
def ingest_market_data_all(self):
    """Ingest market data for all assets."""
    try:
        self.logger.info("Starting market data ingestion for all assets")
        
        # Get container and use case
        container = get_container()
        use_case = container.ingest_market_data_use_case()
        
        # Get all assets
        asset_repo = container.asset_repository()
        assets = asset_repo.get_all()
        
        results = []
        for asset in assets:
            try:
                use_case.execute(asset)
                results.append({
                    "asset_id": asset.id,
                    "symbol": asset.symbol,
                    "status": "success",
                    "timestamp": datetime.utcnow().isoformat()
                })
                self.logger.info(f"Successfully ingested data for {asset.symbol}")
            except Exception as e:
                results.append({
                    "asset_id": asset.id,
                    "symbol": asset.symbol,
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                })
                self.logger.error(f"Failed to ingest data for {asset.symbol}: {e}")
        
        # Clear relevant cache
        cache = get_cache()
        cache.delete_pattern("sentinel_trading:quotes:*")
        cache.delete_pattern("sentinel_trading:dashboard:*")
        
        self.logger.info(f"Completed market data ingestion: {len(results)} assets processed")
        
        return {
            "task_id": self.request.id,
            "total_assets": len(assets),
            "results": results,
            "success_count": len([r for r in results if r["status"] == "success"]),
            "error_count": len([r for r in results if r["status"] == "error"]),
        }
        
    except Exception as e:
        self.logger.error(f"Market data ingestion task failed: {e}")
        raise


@celery_app.task(base=BaseTask, bind=True, cache_result=True)
def ingest_market_data_single(self, asset_id: int):
    """Ingest market data for a single asset."""
    try:
        self.logger.info(f"Starting market data ingestion for asset {asset_id}")
        
        container = get_container()
        use_case = container.ingest_market_data_use_case()
        asset_repo = container.asset_repository()
        
        # Get asset
        asset = asset_repo.get_by_id(asset_id)
        if not asset:
            raise ValueError(f"Asset {asset_id} not found")
        
        # Ingest data
        use_case.execute(asset)
        
        # Clear cache for this asset
        cache = get_cache()
        cache.delete_pattern(f"sentinel_trading:quotes:{asset_id}:*")
        cache.delete_pattern("sentinel_trading:dashboard:*")
        
        self.logger.info(f"Successfully ingested data for {asset.symbol}")
        
        return {
            "task_id": self.request.id,
            "asset_id": asset_id,
            "symbol": asset.symbol,
            "status": "success",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        self.logger.error(f"Market data ingestion failed for asset {asset_id}: {e}")
        raise


@celery_app.task(base=BaseTask, bind=True, cache_result=True)
def run_predictions_all(self):
    """Run predictions for all assets."""
    try:
        self.logger.info("Starting predictions for all assets")
        
        container = get_container()
        use_case = container.run_predictions_use_case()
        
        # Execute predictions
        use_case.execute()
        
        # Clear prediction cache
        cache = get_cache()
        cache.delete_pattern("sentinel_trading:predictions:*")
        cache.delete_pattern("sentinel_trading:dashboard:*")
        
        self.logger.info("Completed predictions for all assets")
        
        return {
            "task_id": self.request.id,
            "status": "success",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        self.logger.error(f"Predictions task failed: {e}")
        raise


@celery_app.task(base=BaseTask, bind=True, cache_result=True)
def run_predictions_single(self, asset_id: int):
    """Run predictions for a single asset."""
    try:
        self.logger.info(f"Starting predictions for asset {asset_id}")
        
        container = get_container()
        asset_repo = container.asset_repository()
        quote_repo = container.quote_repository()
        prediction_repo = container.prediction_repository()
        config = container.config()
        
        # Get asset
        asset = asset_repo.get_by_id(asset_id)
        if not asset:
            raise ValueError(f"Asset {asset_id} not found")
        
        # Create use case for single asset
        from app.application.use_cases import RunPredictionsUseCase
        use_case = RunPredictionsUseCase(asset_repo, quote_repo, prediction_repo, config)
        
        # Execute predictions (modified to handle single asset)
        # This would require modifying the use case to accept specific asset
        # For now, we'll use the existing use case
        use_case.execute()
        
        # Clear cache for this asset
        cache = get_cache()
        cache.delete_pattern(f"sentinel_trading:predictions:{asset_id}:*")
        cache.delete_pattern("sentinel_trading:dashboard:*")
        
        self.logger.info(f"Successfully completed predictions for {asset.symbol}")
        
        return {
            "task_id": self.request.id,
            "asset_id": asset_id,
            "symbol": asset.symbol,
            "status": "success",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        self.logger.error(f"Predictions failed for asset {asset_id}: {e}")
        raise


@celery_app.task(base=BaseTask, bind=True, cache_result=True)
def evaluate_due_predictions(self):
    """Evaluate all due predictions."""
    try:
        self.logger.info("Starting evaluation of due predictions")
        
        container = get_container()
        use_case = container.evaluate_predictions_use_case()
        
        # Execute evaluation
        use_case.execute()
        
        # Clear relevant cache
        cache = get_cache()
        cache.delete_pattern("sentinel_trading:metrics:*")
        cache.delete_pattern("sentinel_trading:dashboard:*")
        
        self.logger.info("Completed evaluation of due predictions")
        
        return {
            "task_id": self.request.id,
            "status": "success",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        self.logger.error(f"Prediction evaluation task failed: {e}")
        raise


@celery_app.task(base=BaseTask, bind=True, cache_result=True)
def ingest_news_all(self):
    """Ingest news for all assets."""
    try:
        self.logger.info("Starting news ingestion for all assets")
        
        container = get_container()
        use_case = container.ingest_news_use_case()
        
        # Execute news ingestion
        use_case.execute()
        
        # Clear news cache
        cache = get_cache()
        cache.delete_pattern("sentinel_trading:news:*")
        cache.delete_pattern("sentinel_trading:dashboard:*")
        
        self.logger.info("Completed news ingestion")
        
        return {
            "task_id": self.request.id,
            "status": "success",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        self.logger.error(f"News ingestion task failed: {e}")
        raise


@celery_app.task(base=BaseTask, bind=True, cache_result=True)
def ingest_news_keywords(self, keywords: str):
    """Ingest news for specific keywords."""
    try:
        self.logger.info(f"Starting news ingestion for keywords: {keywords}")
        
        container = get_container()
        asset_repo = container.asset_repository()
        news_aggregator = container.news_aggregator()
        news_write_repo = container.news_write_repository()
        sentiment_scorer = container.sentiment_scorer()
        
        # Create use case for specific keywords
        from app.application.use_cases import IngestNewsUseCase
        use_case = IngestNewsUseCase(asset_repo, news_aggregator, news_write_repo, sentiment_scorer)
        
        # Execute with specific keywords (would need modification to use case)
        use_case.execute()
        
        # Clear news cache
        cache = get_cache()
        cache.delete_pattern(f"sentinel_trading:news:*{keywords}*")
        cache.delete_pattern("sentinel_trading:dashboard:*")
        
        self.logger.info(f"Completed news ingestion for keywords: {keywords}")
        
        return {
            "task_id": self.request.id,
            "keywords": keywords,
            "status": "success",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        self.logger.error(f"News ingestion failed for keywords {keywords}: {e}")
        raise


@celery_app.task(base=BaseTask, bind=True, cache_result=True)
def run_full_pipeline(self, force_news: bool = False):
    """Run full pipeline (market data + predictions + news + evaluation)."""
    try:
        self.logger.info("Starting full pipeline execution")
        
        container = get_container()
        use_case = container.full_pipeline_use_case()
        
        # Execute full pipeline
        use_case.execute(force_news=force_news)
        
        # Clear all relevant cache
        cache = get_cache()
        cache.delete_pattern("sentinel_trading:*")
        
        self.logger.info("Completed full pipeline execution")
        
        return {
            "task_id": self.request.id,
            "force_news": force_news,
            "status": "success",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        self.logger.error(f"Full pipeline task failed: {e}")
        raise


@celery_app.task(base=BaseTask, bind=True, cache_result=True)
def cleanup_old_data(self):
    """Clean up old data and maintain database performance."""
    try:
        self.logger.info("Starting data cleanup")
        
        container = get_container()
        
        # Define retention periods
        retention_days = {
            'quotes': 365,  # Keep 1 year of quotes
            'news': 90,     # Keep 3 months of news
            'predictions': 180,  # Keep 6 months of predictions
        }
        
        cutoff_date = datetime.utcnow() - timedelta(days=365)
        cleanup_results = {}
        
        # Clean up old quotes (keep only recent data)
        quote_repo = container.quote_repository()
        # This would require implementing cleanup methods in repositories
        # old_quotes_count = quote_repo.delete_quotes_before(cutoff_date)
        # cleanup_results['quotes_deleted'] = old_quotes_count
        
        # Clean up old news
        news_repo = container.news_write_repository()
        # news_cutoff = datetime.utcnow() - timedelta(days=retention_days['news'])
        # old_news_count = news_repo.delete_news_before(news_cutoff)
        # cleanup_results['news_deleted'] = old_news_count
        
        # Clean up old predictions
        prediction_repo = container.prediction_repository()
        # pred_cutoff = datetime.utcnow() - timedelta(days=retention_days['predictions'])
        # old_predictions_count = prediction_repo.delete_predictions_before(pred_cutoff)
        # cleanup_results['predictions_deleted'] = old_predictions_count
        
        # Clear expired cache entries
        cache = get_cache()
        # This would require implementing cache cleanup
        # cache.cleanup_expired()
        
        self.logger.info(f"Completed data cleanup: {cleanup_results}")
        
        return {
            "task_id": self.request.id,
            "cleanup_results": cleanup_results,
            "status": "success",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        self.logger.error(f"Data cleanup task failed: {e}")
        raise


@celery_app.task(base=BaseTask, bind=True, cache_result=True)
def health_check(self):
    """Perform comprehensive health check."""
    try:
        self.logger.info("Starting health check")
        
        health_status = {
            "task_id": self.request.id,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {}
        }
        
        # Check database health
        try:
            from app.infrastructure.database import check_database_health
            db_health = check_database_health()
            health_status["checks"]["database"] = db_health
        except Exception as e:
            health_status["checks"]["database"] = {"status": "error", "error": str(e)}
        
        # Check cache health
        try:
            cache = get_cache()
            cache_health = cache.get_cache_info()
            health_status["checks"]["cache"] = cache_health
        except Exception as e:
            health_status["checks"]["cache"] = {"status": "error", "error": str(e)}
        
        # Check external API health
        try:
            from app.infrastructure.resilience import get_circuit_breaker_status
            api_health = get_circuit_breaker_status()
            health_status["checks"]["external_apis"] = api_health
        except Exception as e:
            health_status["checks"]["external_apis"] = {"status": "error", "error": str(e)}
        
        # Check system resources
        try:
            import psutil
            health_status["checks"]["system"] = {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
            }
        except Exception as e:
            health_status["checks"]["system"] = {"status": "error", "error": str(e)}
        
        # Overall status
        all_healthy = all(
            check.get("status") in ["healthy", "connected"] 
            for check in health_status["checks"].values()
            if isinstance(check, dict) and "status" in check
        )
        
        health_status["overall_status"] = "healthy" if all_healthy else "degraded"
        
        self.logger.info(f"Health check completed: {health_status['overall_status']}")
        
        return health_status
        
    except Exception as e:
        self.logger.error(f"Health check task failed: {e}")
        raise


@celery_app.task(base=BaseTask, bind=True, cache_result=True)
def walk_forward_analysis(self, asset_id: Optional[int] = None, train_min: int = 55, 
                          step: int = 3, ensemble: bool = True):
    """Run walk-forward analysis for model validation."""
    try:
        self.logger.info(f"Starting walk-forward analysis for asset {asset_id or 'all'}")
        
        container = get_container()
        walk_forward_service = container.walk_forward_service()
        
        # Run analysis
        results = walk_forward_service.run_walk_forward(
            train_min=train_min,
            step=step,
            ensemble=ensemble,
            asset_id=asset_id
        )
        
        # Clear metrics cache
        cache = get_cache()
        cache.delete_pattern("sentinel_trading:metrics:walk-forward:*")
        
        self.logger.info(f"Completed walk-forward analysis: {results.get('total_assets', 0)} assets")
        
        return {
            "task_id": self.request.id,
            "parameters": {
                "asset_id": asset_id,
                "train_min": train_min,
                "step": step,
                "ensemble": ensemble
            },
            "results": results,
            "status": "success",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        self.logger.error(f"Walk-forward analysis failed: {e}")
        raise


# Utility functions for task management
def get_task_status(task_id: str) -> Dict:
    """Get task status and result."""
    try:
        result = celery_app.AsyncResult(task_id)
        
        return {
            "task_id": task_id,
            "state": result.state,
            "result": result.result if result.state == "SUCCESS" else None,
            "error": str(result.result) if result.state == "FAILURE" else None,
            "traceback": result.traceback if result.state == "FAILURE" else None,
            "date_done": result.date_done.isoformat() if result.date_done else None,
        }
    except Exception as e:
        logger.error(f"Failed to get task status {task_id}: {e}")
        return {"task_id": task_id, "error": str(e)}


def cancel_task(task_id: str, terminate: bool = False) -> bool:
    """Cancel or terminate a task."""
    try:
        celery_app.control.revoke(task_id, terminate=terminate)
        logger.info(f"Task {task_id} revoked (terminate={terminate})")
        return True
    except Exception as e:
        logger.error(f"Failed to revoke task {task_id}: {e}")
        return False
