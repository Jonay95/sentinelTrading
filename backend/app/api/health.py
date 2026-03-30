"""
Health check endpoints for Sentinel Trading application.
"""

import logging
from datetime import datetime
from flask import Blueprint, jsonify, request
from sqlalchemy import text

from app.infrastructure.database import get_db_manager
from app.infrastructure.cache import get_cache
from app.infrastructure.resilience import get_circuit_breaker_status
from app.infrastructure.celery_app import check_celery_health, get_task_monitor
from app.infrastructure.logging_config import LoggerMixin

logger = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__, url_prefix='/health')


class HealthChecker(LoggerMixin):
    """Comprehensive health checker for all system components."""
    
    def __init__(self):
        self.db_manager = get_db_manager()
        self.cache = get_cache()
    
    def check_database(self) -> dict:
        """Check database connectivity and performance."""
        try:
            if not self.db_manager:
                return {
                    "status": "unhealthy",
                    "error": "Database manager not initialized",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Use existing health check
            health = self.db_manager.health_check()
            
            # Add additional checks
            if health.get("status") == "healthy":
                # Test query performance
                with self.db_manager.get_session() as session:
                    start_time = datetime.utcnow()
                    result = session.execute(text("SELECT COUNT(*) FROM assets")).scalar()
                    query_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                    
                    health["query_performance_ms"] = query_time
                    health["asset_count"] = result
                    
                    # Slow query warning
                    if query_time > 100:
                        health["status"] = "degraded"
                        health["warning"] = "Slow database queries detected"
            
            return health
            
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def check_cache(self) -> dict:
        """Check Redis cache connectivity and performance."""
        try:
            if not self.cache:
                return {
                    "status": "unhealthy",
                    "error": "Cache manager not initialized",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Test cache operations
            test_key = "health_check_test"
            test_value = {"test": True, "timestamp": datetime.utcnow().isoformat()}
            
            # Test set
            start_time = datetime.utcnow()
            set_success = self.cache.set(test_key, test_value, ttl=10)
            set_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Test get
            start_time = datetime.utcnow()
            retrieved_value = self.cache.get(test_key)
            get_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Clean up
            self.cache.delete(test_key)
            
            if not set_success or retrieved_value != test_value:
                return {
                    "status": "unhealthy",
                    "error": "Cache read/write test failed",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Get cache info
            cache_info = self.cache.get_cache_info()
            
            health = {
                "status": "healthy",
                "set_time_ms": round(set_time, 2),
                "get_time_ms": round(get_time, 2),
                "cache_info": cache_info,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Performance warnings
            if set_time > 50 or get_time > 50:
                health["status"] = "degraded"
                health["warning"] = "Slow cache operations detected"
            
            return health
            
        except Exception as e:
            self.logger.error(f"Cache health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def check_external_apis(self) -> dict:
        """Check external API circuit breaker status."""
        try:
            circuit_status = get_circuit_breaker_status()
            
            # Determine overall status
            healthy_services = sum(1 for status in circuit_status.values() if status == "CLOSED")
            total_services = len(circuit_status)
            
            if healthy_services == total_services:
                overall_status = "healthy"
            elif healthy_services > 0:
                overall_status = "degraded"
            else:
                overall_status = "unhealthy"
            
            return {
                "status": overall_status,
                "services": circuit_status,
                "healthy_services": healthy_services,
                "total_services": total_services,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"External API health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def check_celery(self) -> dict:
        """Check Celery worker status."""
        try:
            return check_celery_health()
        except Exception as e:
            self.logger.error(f"Celery health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def check_system_resources(self) -> dict:
        """Check system resource usage."""
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk usage
            disk = psutil.disk_usage('/')
            
            # Network connections
            network = psutil.net_connections()
            active_connections = len([conn for conn in network if conn.status == 'ESTABLISHED'])
            
            health = {
                "status": "healthy",
                "cpu": {
                    "percent": cpu_percent,
                    "count": psutil.cpu_count(),
                },
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "percent": memory.percent,
                    "used_gb": round(memory.used / (1024**3), 2),
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "percent": disk.percent,
                    "used_gb": round(disk.used / (1024**3), 2),
                },
                "network": {
                    "active_connections": active_connections,
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Determine overall status based on resource usage
            if cpu_percent > 90 or memory.percent > 90 or disk.percent > 95:
                health["status"] = "critical"
            elif cpu_percent > 70 or memory.percent > 70 or disk.percent > 80:
                health["status"] = "degraded"
            
            return health
            
        except Exception as e:
            self.logger.error(f"System resource check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def comprehensive_health_check(self) -> dict:
        """Perform comprehensive health check of all components."""
        checks = {
            "database": self.check_database(),
            "cache": self.check_cache(),
            "external_apis": self.check_external_apis(),
            "celery": self.check_celery(),
            "system": self.check_system_resources(),
        }
        
        # Determine overall status
        statuses = [check.get("status", "unknown") for check in checks.values()]
        
        if all(status == "healthy" for status in statuses):
            overall_status = "healthy"
        elif any(status == "unhealthy" for status in statuses):
            overall_status = "unhealthy"
        else:
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "checks": checks,
            "summary": {
                "total_checks": len(checks),
                "healthy": len([s for s in statuses if s == "healthy"]),
                "degraded": len([s for s in statuses if s == "degraded"]),
                "unhealthy": len([s for s in statuses if s == "unhealthy"]),
            },
            "timestamp": datetime.utcnow().isoformat()
        }


# Global health checker instance
health_checker = HealthChecker()


@health_bp.route('/')
def basic_health():
    """Basic health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "sentinel-trading-api",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    })


@health_bp.route('/ready')
def readiness_check():
    """Readiness check for Kubernetes/container orchestration."""
    # Check critical dependencies
    db_health = health_checker.check_database()
    cache_health = health_checker.check_cache()
    
    if db_health.get("status") == "healthy" and cache_health.get("status") == "healthy":
        return jsonify({
            "status": "ready",
            "checks": {
                "database": db_health["status"],
                "cache": cache_health["status"],
            },
            "timestamp": datetime.utcnow().isoformat()
        }), 200
    else:
        return jsonify({
            "status": "not_ready",
            "checks": {
                "database": db_health["status"],
                "cache": cache_health["status"],
            },
            "timestamp": datetime.utcnow().isoformat()
        }), 503


@health_bp.route('/live')
def liveness_check():
    """Liveness check for Kubernetes/container orchestration."""
    # Simple check - if we can respond, we're alive
    return jsonify({
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat()
    }), 200


@health_bp.route('/comprehensive')
def comprehensive_health():
    """Comprehensive health check of all components."""
    try:
        health_data = health_checker.comprehensive_health_check()
        
        # Return appropriate HTTP status code
        status_code = 200
        if health_data["status"] == "unhealthy":
            status_code = 503
        elif health_data["status"] == "degraded":
            status_code = 200  # Still serve traffic but indicate issues
        
        return jsonify(health_data), status_code
        
    except Exception as e:
        logger.error(f"Comprehensive health check failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@health_bp.route('/database')
def database_health():
    """Database-specific health check."""
    health = health_checker.check_database()
    status_code = 200 if health.get("status") == "healthy" else 503
    return jsonify(health), status_code


@health_bp.route('/cache')
def cache_health():
    """Cache-specific health check."""
    health = health_checker.check_cache()
    status_code = 200 if health.get("status") == "healthy" else 503
    return jsonify(health), status_code


@health_bp.route('/external-apis')
def external_apis_health():
    """External APIs health check."""
    health = health_checker.check_external_apis()
    status_code = 200 if health.get("status") in ["healthy", "degraded"] else 503
    return jsonify(health), status_code


@health_bp.route('/celery')
def celery_health():
    """Celery-specific health check."""
    health = health_checker.check_celery()
    status_code = 200 if health.get("status") in ["healthy", "degraded"] else 503
    return jsonify(health), status_code


@health_bp.route('/system')
def system_health():
    """System resource health check."""
    health = health_checker.check_system_resources()
    status_code = 200 if health.get("status") in ["healthy", "degraded"] else 503
    return jsonify(health), status_code


@health_bp.route('/tasks')
def tasks_status():
    """Get status of Celery tasks."""
    try:
        task_monitor = get_task_monitor()
        
        active_tasks = task_monitor.get_active_tasks()
        scheduled_tasks = task_monitor.get_scheduled_tasks()
        worker_stats = task_monitor.get_worker_stats()
        queue_info = task_monitor.get_queue_info()
        
        return jsonify({
            "active_tasks": active_tasks,
            "scheduled_tasks": scheduled_tasks,
            "worker_stats": worker_stats,
            "queue_info": queue_info,
            "timestamp": datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Task status check failed: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@health_bp.route('/metrics')
def health_metrics():
    """Health metrics for monitoring systems."""
    try:
        comprehensive = health_checker.comprehensive_health_check()
        
        # Extract key metrics for monitoring
        metrics = {
            "status": comprehensive["status"],
            "database_response_time_ms": comprehensive["checks"]["database"].get("query_performance_ms"),
            "cache_hit_rate": comprehensive["checks"]["cache"].get("cache_info", {}).get("hit_rate", 0),
            "cpu_percent": comprehensive["checks"]["system"].get("cpu", {}).get("percent", 0),
            "memory_percent": comprehensive["checks"]["system"].get("memory", {}).get("percent", 0),
            "disk_percent": comprehensive["checks"]["system"].get("disk", {}).get("percent", 0),
            "healthy_services": comprehensive["summary"]["healthy"],
            "degraded_services": comprehensive["summary"]["degraded"],
            "unhealthy_services": comprehensive["summary"]["unhealthy"],
            "timestamp": comprehensive["timestamp"]
        }
        
        return jsonify(metrics), 200
        
    except Exception as e:
        logger.error(f"Health metrics check failed: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500
