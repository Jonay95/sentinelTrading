"""
Celery configuration and tasks for Sentinel Trading async processing.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from celery import Celery, Task
from celery.signals import task_prerun, task_postrun, task_failure, task_success
from celery.schedules import crontab
import redis

from app.config import Config
from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache

logger = logging.getLogger(__name__)


class CeleryConfig:
    """Celery configuration settings."""
    
    # Broker configuration
    BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/1')
    RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')
    
    # Task settings
    TASK_SERIALIZER = 'json'
    RESULT_SERIALIZER = 'json'
    ACCEPT_CONTENT = ['json']
    RESULT_EXPIRES = 3600  # 1 hour
    TASK_TRACK_STARTED = True
    TASK_TIME_LIMIT = 300  # 5 minutes
    TASK_SOFT_TIME_LIMIT = 240  # 4 minutes
    WORKER_PREFETCH_MULTIPLIER = 1
    WORKER_MAX_TASKS_PER_CHILD = 1000
    
    # Beat scheduler settings
    BEAT_SCHEDULE = {
        # Daily market data ingestion at 8 AM UTC
        'ingest-market-data-daily': {
            'task': 'app.infrastructure.celery_tasks.ingest_market_data_all',
            'schedule': crontab(hour=8, minute=0),
            'options': {'queue': 'market_data'}
        },
        
        # Run predictions every 6 hours
        'run-predictions-every-6h': {
            'task': 'app.infrastructure.celery_tasks.run_predictions_all',
            'schedule': crontab(minute='*/360'),  # Every 6 hours
            'options': {'queue': 'predictions'}
        },
        
        # Evaluate predictions every hour
        'evaluate-predictions-hourly': {
            'task': 'app.infrastructure.celery_tasks.evaluate_due_predictions',
            'schedule': crontab(minute=0),  # Every hour
            'options': {'queue': 'evaluations'}
        },
        
        # Ingest news every 2 hours
        'ingest-news-every-2h': {
            'task': 'app.infrastructure.celery_tasks.ingest_news_all',
            'schedule': crontab(minute='*/120'),  # Every 2 hours
            'options': {'queue': 'news'}
        },
        
        # Clean up old data daily at 2 AM UTC
        'cleanup-old-data-daily': {
            'task': 'app.infrastructure.celery_tasks.cleanup_old_data',
            'schedule': crontab(hour=2, minute=0),
            'options': {'queue': 'maintenance'}
        },
        
        # Health check every 5 minutes
        'health-check-every-5m': {
            'task': 'app.infrastructure.celery_tasks.health_check',
            'schedule': crontab(minute='*/5'),
            'options': {'queue': 'monitoring'}
        },
    }


def _build_full_beat_schedule() -> Dict[str, Any]:
    """
    Beat schedule base + tarea opcional registro_cita (intervalo desde .env).

    REGISTRO_CITA_BEAT_ENABLED: true/false (defecto true). false desactiva el beat.
    REGISTRO_CITA_BEAT_INTERVAL_MINUTES: entero 1–1440 (defecto 1).
    Solo se programa en Beat si REGISTRO_CITA_URL no está vacía (evita ejecuciones vacías).
    """
    schedule = dict(CeleryConfig.BEAT_SCHEDULE)
    enabled_raw = (os.environ.get("REGISTRO_CITA_BEAT_ENABLED") or "true").strip().lower()
    if enabled_raw in ("0", "false", "no", "off"):
        return schedule
    if not (os.environ.get("REGISTRO_CITA_URL") or "").strip():
        return schedule
    try:
        minutes = int(os.environ.get("REGISTRO_CITA_BEAT_INTERVAL_MINUTES", "1") or "1")
    except ValueError:
        minutes = 1
    minutes = max(1, min(minutes, 1440))
    schedule["registro-cita-periodic"] = {
        "task": "app.utils.tasks.registro_cita.registro_cita",
        "schedule": timedelta(minutes=minutes),
    }
    return schedule


# Create Celery app
celery_app = Celery('sentinel_trading')
celery_app.config_from_object(CeleryConfig)

# Auto-discover tasks
celery_app.autodiscover_tasks(['app.infrastructure'])

_beat_schedule = _build_full_beat_schedule()
celery_app.conf.beat_schedule = _beat_schedule

# Diagnóstico al cargar la app (visible en logs de `celery beat` y `celery worker`).
_reg_en = (os.environ.get("REGISTRO_CITA_BEAT_ENABLED") or "true").strip().lower()
if _reg_en in ("0", "false", "no", "off"):
    logger.warning(
        "Celery: registro_cita no está en el beat (REGISTRO_CITA_BEAT_ENABLED desactivado)."
    )
elif not (os.environ.get("REGISTRO_CITA_URL") or "").strip():
    logger.warning(
        "Celery: registro_cita no está en el beat: falta REGISTRO_CITA_URL en las variables "
        "de entorno de este proceso. En Render, configúrala también en sentinel-celery-beat "
        "(no solo en el API o en el worker)."
    )
elif "registro-cita-periodic" in _beat_schedule:
    _reg_sched = _beat_schedule["registro-cita-periodic"]["schedule"]
    if isinstance(_reg_sched, timedelta):
        logger.info(
            "Celery: registro-cita-periodic cada %.0f minutos.",
            _reg_sched.total_seconds() / 60.0,
        )
    else:
        logger.info("Celery: registro-cita-periodic programada (%s).", _reg_sched)


class BaseTask(Task, LoggerMixin):
    """Base task with logging and error handling."""
    
    def __init__(self):
        super().__init__()
        self.cache = get_cache()
    
    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds."""
        self.logger.info(f"Task {self.name} completed successfully")
        
        # Cache result if applicable
        if hasattr(self, 'cache_result') and self.cache_result:
            cache_key = f"task_result:{self.name}:{task_id}"
            self.cache.set(cache_key, retval, ttl=300)  # 5 minutes
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails."""
        self.logger.error(f"Task {self.name} failed: {exc}")
        
        # Cache error for debugging
        if hasattr(self, 'cache_result') and self.cache_result:
            cache_key = f"task_error:{self.name}:{task_id}"
            error_data = {
                "error": str(exc),
                "traceback": str(einfo),
                "timestamp": datetime.utcnow().isoformat()
            }
            self.cache.set(cache_key, error_data, ttl=3600)  # 1 hour
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called when task is retried."""
        self.logger.warning(f"Task {self.name} retrying: {exc}")


# Signal handlers for task monitoring
@task_prerun.connect
def task_prerun_handler(task_id, task, *args, **kwargs):
    """Log task start."""
    logger.info(f"Starting task: {task.name}[{task_id}]")


@task_postrun.connect
def task_postrun_handler(task_id, task, *args, **kwargs):
    """Log task completion."""
    logger.info(f"Completed task: {task.name}[{task_id}]")


@task_success.connect
def task_success_handler(sender, result=None, **kwargs):
    """Log task success."""
    logger.info(f"Task succeeded: {sender.name}")


@task_failure.connect
def task_failure_handler(sender, task_id, exception, **kwargs):
    """Log task failure."""
    logger.error(f"Task failed: {sender.name}[{task_id}] - {exception}")


class TaskMonitor(LoggerMixin):
    """Monitor and manage Celery tasks."""
    
    def __init__(self, celery_app: Celery):
        self.celery_app = celery_app
        self.cache = get_cache()
    
    def get_active_tasks(self) -> List[Dict]:
        """Get list of currently active tasks."""
        try:
            inspect = self.celery_app.control.inspect()
            active_tasks = inspect.active()
            
            tasks = []
            for worker, task_list in (active_tasks or {}).items():
                for task in task_list:
                    tasks.append({
                        "worker": worker,
                        "id": task.get("id"),
                        "name": task.get("name"),
                        "args": task.get("args"),
                        "kwargs": task.get("kwargs"),
                        "time_start": task.get("time_start"),
                    })
            
            return tasks
        except Exception as e:
            self.logger.error(f"Failed to get active tasks: {e}")
            return []
    
    def get_scheduled_tasks(self) -> List[Dict]:
        """Get list of scheduled tasks."""
        try:
            inspect = self.celery_app.control.inspect()
            scheduled_tasks = inspect.scheduled()
            
            tasks = []
            for worker, task_list in (scheduled_tasks or {}).items():
                for task in task_list:
                    tasks.append({
                        "worker": worker,
                        "id": task.get("id"),
                        "name": task.get("name"),
                        "args": task.get("args"),
                        "kwargs": task.get("kwargs"),
                        "eta": task.get("eta"),
                    })
            
            return tasks
        except Exception as e:
            self.logger.error(f"Failed to get scheduled tasks: {e}")
            return []
    
    def get_worker_stats(self) -> Dict:
        """Get worker statistics."""
        try:
            inspect = self.celery_app.control.inspect()
            stats = inspect.stats()
            
            return stats or {}
        except Exception as e:
            self.logger.error(f"Failed to get worker stats: {e}")
            return {}
    
    def revoke_task(self, task_id: str, terminate: bool = False) -> bool:
        """Revoke a task."""
        try:
            self.celery_app.control.revoke(task_id, terminate=terminate)
            self.logger.info(f"Revoked task: {task_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to revoke task {task_id}: {e}")
            return False
    
    def get_task_result(self, task_id: str) -> Any:
        """Get task result."""
        try:
            result = self.celery_app.AsyncResult(task_id)
            return result.get(timeout=5)
        except Exception as e:
            self.logger.error(f"Failed to get task result {task_id}: {e}")
            return None
    
    def get_queue_info(self) -> Dict:
        """Get queue information."""
        try:
            with self.celery_app.connection() as conn:
                channel = conn.channel()
                
                queue_info = {}
                for queue_name in ['market_data', 'predictions', 'evaluations', 'news', 'maintenance', 'monitoring']:
                    try:
                        queue = channel.queue_declare(queue_name, passive=True)
                        queue_info[queue_name] = {
                            "message_count": queue.message_count,
                            "consumer_count": queue.consumer_count,
                        }
                    except Exception:
                        queue_info[queue_name] = {"message_count": 0, "consumer_count": 0}
                
                return queue_info
        except Exception as e:
            self.logger.error(f"Failed to get queue info: {e}")
            return {}


class TaskScheduler(LoggerMixin):
    """Schedule and manage recurring tasks."""
    
    def __init__(self, celery_app: Celery):
        self.celery_app = celery_app
    
    def schedule_market_data_ingestion(self, asset_ids: List[int] = None, delay: int = 0):
        """Schedule market data ingestion."""
        from app.infrastructure.celery_tasks import ingest_market_data_all, ingest_market_data_single
        
        if asset_ids is None:
            # Schedule for all assets
            task = ingest_market_data_all.apply_async(
                countdown=delay,
                queue='market_data'
            )
        else:
            # Schedule for specific assets
            for asset_id in asset_ids:
                ingest_market_data_single.apply_async(
                    args=[asset_id],
                    countdown=delay,
                    queue='market_data'
                )
        
        self.logger.info(f"Scheduled market data ingestion for {len(asset_ids) if asset_ids else 'all'} assets")
    
    def schedule_predictions(self, asset_ids: List[int] = None, delay: int = 0):
        """Schedule prediction runs."""
        from app.infrastructure.celery_tasks import run_predictions_all, run_predictions_single
        
        if asset_ids is None:
            # Schedule for all assets
            task = run_predictions_all.apply_async(
                countdown=delay,
                queue='predictions'
            )
        else:
            # Schedule for specific assets
            for asset_id in asset_ids:
                run_predictions_single.apply_async(
                    args=[asset_id],
                    countdown=delay,
                    queue='predictions'
                )
        
        self.logger.info(f"Scheduled predictions for {len(asset_ids) if asset_ids else 'all'} assets")
    
    def schedule_news_ingestion(self, keywords: str = None, delay: int = 0):
        """Schedule news ingestion."""
        from app.infrastructure.celery_tasks import ingest_news_all, ingest_news_keywords
        
        if keywords:
            task = ingest_news_keywords.apply_async(
                args=[keywords],
                countdown=delay,
                queue='news'
            )
        else:
            task = ingest_news_all.apply_async(
                countdown=delay,
                queue='news'
            )
        
        self.logger.info(f"Scheduled news ingestion for keywords: {keywords or 'all'}")
    
    def schedule_full_pipeline(self, delay: int = 0):
        """Schedule full pipeline run."""
        from app.infrastructure.celery_tasks import run_full_pipeline
        
        task = run_full_pipeline.apply_async(
            countdown=delay,
            queue='maintenance'
        )
        
        self.logger.info("Scheduled full pipeline run")
        return task


# Global instances
task_monitor = TaskMonitor(celery_app)
task_scheduler = TaskScheduler(celery_app)


def init_celery(app=None):
    """Initialize Celery with Flask app."""
    if app:
        celery_app.conf.update(app.config)
    
    return celery_app


def get_celery_app() -> Celery:
    """Get Celery app instance."""
    return celery_app


def get_task_monitor() -> TaskMonitor:
    """Get task monitor instance."""
    return task_monitor


def get_task_scheduler() -> TaskScheduler:
    """Get task scheduler instance."""
    return task_scheduler


# Health check for Celery
def check_celery_health() -> Dict:
    """Check Celery health."""
    try:
        # Check if workers are available
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        
        if not stats:
            return {
                "status": "unhealthy",
                "error": "No workers available",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Check broker connection
        try:
            celery_app.connection().ensure_connection(max_retries=1)
            broker_status = "connected"
        except Exception:
            broker_status = "disconnected"
        
        return {
            "status": "healthy" if broker_status == "connected" else "degraded",
            "broker_status": broker_status,
            "workers": list(stats.keys()),
            "worker_count": len(stats),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Celery health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


# Registrar tareas que no siguen el patrón autodiscover (celery_tasks / registro_cita)
import app.infrastructure.celery_tasks  # noqa: E402, F401
import app.utils.tasks.registro_cita  # noqa: E402, F401
