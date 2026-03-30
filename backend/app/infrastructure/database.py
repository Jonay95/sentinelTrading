"""
Database connection pooling and configuration for Sentinel Trading.
"""

import logging
from contextlib import contextmanager
from typing import Optional, Generator
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.engine.pool import QueuePool
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy_utils import database_exists, create_database
import time

from app.config import Config
from app.extensions import db
from app.infrastructure.logging_config import LoggerMixin

logger = logging.getLogger(__name__)


class DatabaseManager(LoggerMixin):
    """Enhanced database manager with connection pooling and monitoring."""
    
    def __init__(self, config: Config):
        self.config = config
        self.engine: Optional[Engine] = None
        self.session_factory: Optional[sessionmaker] = None
        self._pool_stats = {
            "total_connections": 0,
            "active_connections": 0,
            "idle_connections": 0,
            "overflow_connections": 0,
        }
    
    def create_engine_with_pooling(self) -> Engine:
        """Create SQLAlchemy engine with optimized connection pooling."""
        # Database URL from config
        database_url = getattr(self.config, 'DATABASE_URL', 'sqlite:///sentinel_trading.db')
        
        # Engine configuration for production
        engine_kwargs = {
            "poolclass": QueuePool,
            "pool_size": 10,  # Number of connections to keep open
            "max_overflow": 20,  # Additional connections beyond pool_size
            "pool_timeout": 30,  # Timeout for getting connection from pool
            "pool_recycle": 3600,  # Recycle connections every hour
            "pool_pre_ping": True,  # Validate connections before use
            "echo": getattr(self.config, 'SQL_DEBUG', False),  # SQL logging
        }
        
        # SQLite-specific optimizations
        if database_url.startswith('sqlite'):
            engine_kwargs.update({
                "connect_args": {
                    "check_same_thread": False,
                    "timeout": 20,
                    "isolation_level": None,  # Autocommit mode for SQLite
                },
                "poolclass": None,  # SQLite doesn't use connection pooling
                "pool_pre_ping": False,
            })
        else:
            # PostgreSQL/MySQL specific settings
            engine_kwargs.update({
                "connect_args": {
                    "connect_timeout": 10,
                    "application_name": "sentinel_trading",
                },
                "isolation_level": "READ_COMMITTED",
            })
        
        engine = create_engine(database_url, **engine_kwargs)
        
        # Add event listeners for monitoring
        self._setup_engine_listeners(engine)
        
        self.engine = engine
        self.logger.info(f"Database engine created with pooling: {database_url}")
        
        return engine
    
    def _setup_engine_listeners(self, engine: Engine):
        """Setup event listeners for connection monitoring."""
        
        @event.listens_for(engine, "connect")
        def receive_connect(dbapi_connection, connection_record):
            """Called when a connection is established."""
            self._pool_stats["total_connections"] += 1
            self.logger.debug("Database connection established")
        
        @event.listens_for(engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            """Called when a connection is checked out from pool."""
            self._pool_stats["active_connections"] += 1
            self._pool_stats["idle_connections"] -= 1
            self.logger.debug("Database connection checked out")
        
        @event.listens_for(engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            """Called when a connection is returned to pool."""
            self._pool_stats["active_connections"] -= 1
            self._pool_stats["idle_connections"] += 1
            self.logger.debug("Database connection checked in")
        
        @event.listens_for(engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Called before SQL execution."""
            context._query_start_time = time.time()
        
        @event.listens_for(engine, "after_cursor_execute")
        def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Called after SQL execution."""
            if hasattr(context, '_query_start_time'):
                duration = (time.time() - context._query_start_time) * 1000
                if duration > 1000:  # Log slow queries (> 1s)
                    self.logger.warning(f"Slow query ({duration:.2f}ms): {statement[:100]}...")
    
    def create_session_factory(self):
        """Create session factory with optimized settings."""
        if not self.engine:
            raise RuntimeError("Engine not initialized")
        
        session_factory = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
        
        self.session_factory = session_factory
        return session_factory
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get database session with automatic cleanup."""
        if not self.session_factory:
            raise RuntimeError("Session factory not initialized")
        
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def initialize_database(self):
        """Initialize database if it doesn't exist."""
        database_url = getattr(self.config, 'DATABASE_URL', 'sqlite:///sentinel_trading.db')
        
        if database_url.startswith('sqlite'):
            # SQLite: create directory if needed
            import os
            db_path = database_url.replace('sqlite:///', '')
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        else:
            # PostgreSQL/MySQL: create database if it doesn't exist
            if not database_exists(database_url):
                create_database(database_url)
                self.logger.info(f"Created database: {database_url}")
    
    def get_pool_status(self) -> dict:
        """Get current connection pool status."""
        if not self.engine:
            return {"status": "not_initialized"}
        
        pool = self.engine.pool
        if pool is None:
            return {"status": "no_pool"}
        
        return {
            "status": "active",
            "pool_size": getattr(pool, 'size', 0),
            "checked_in": getattr(pool, 'checkedin', 0),
            "checked_out": getattr(pool, 'checkedout', 0),
            "overflow": getattr(pool, 'overflow', 0),
            "invalid": getattr(pool, 'invalid', 0),
            "custom_stats": self._pool_stats,
        }
    
    def health_check(self) -> dict:
        """Perform database health check."""
        try:
            with self.get_session() as session:
                # Simple query to test connection
                result = session.execute("SELECT 1").scalar()
                
                pool_status = self.get_pool_status()
                
                return {
                    "status": "healthy",
                    "connection_test": result == 1,
                    "pool_status": pool_status,
                    "timestamp": time.time(),
                }
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time(),
            }


class DatabaseMigrator(LoggerMixin):
    """Database migration manager with rollback capabilities."""
    
    def __init__(self, engine: Engine):
        self.engine = engine
    
    def run_migrations(self, migration_directory: str = "migrations"):
        """Run database migrations."""
        try:
            from flask_migrate import upgrade, current
            from flask import current_app
            
            with current_app.app_context():
                # Get current revision
                current_rev = current()
                self.logger.info(f"Current database revision: {current_rev}")
                
                # Run migrations
                upgrade()
                
                # Get new revision
                new_rev = current()
                self.logger.info(f"Database migrated to revision: {new_rev}")
                
                return True
        except Exception as e:
            self.logger.error(f"Migration failed: {e}")
            return False
    
    def rollback_migration(self, revision: str = None):
        """Rollback to specific revision."""
        try:
            from flask_migrate import downgrade, current
            from flask import current_app
            
            with current_app.app_context():
                current_rev = current()
                self.logger.info(f"Rolling back from revision: {current_rev}")
                
                if revision:
                    downgrade(revision)
                else:
                    downgrade()  # Rollback one revision
                
                new_rev = current()
                self.logger.info(f"Rolled back to revision: {new_rev}")
                
                return True
        except Exception as e:
            self.logger.error(f"Rollback failed: {e}")
            return False


class DatabaseIndexManager(LoggerMixin):
    """Manager for database indexes and performance optimization."""
    
    def __init__(self, engine: Engine):
        self.engine = engine
    
    def create_performance_indexes(self):
        """Create indexes for frequently queried columns."""
        indexes = [
            # Asset indexes
            "CREATE INDEX IF NOT EXISTS idx_assets_symbol ON assets(symbol);",
            "CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type);",
            "CREATE INDEX IF NOT EXISTS idx_assets_provider ON assets(provider);",
            
            # Quotes indexes
            "CREATE INDEX IF NOT EXISTS idx_quotes_asset_ts ON quotes(asset_id, timestamp DESC);",
            "CREATE INDEX IF NOT EXISTS idx_quotes_timestamp ON quotes(timestamp DESC);",
            "CREATE INDEX IF NOT EXISTS idx_quotes_asset_id ON quotes(asset_id);",
            
            # Predictions indexes
            "CREATE INDEX IF NOT EXISTS idx_predictions_asset_target ON predictions(asset_id, target_date DESC);",
            "CREATE INDEX IF NOT EXISTS idx_predictions_target_date ON predictions(target_date DESC);",
            "CREATE INDEX IF NOT EXISTS idx_predictions_created_at ON predictions(created_at DESC);",
            
            # News indexes
            "CREATE INDEX IF NOT EXISTS idx_news_published_at ON news_articles(published_at DESC);",
            "CREATE INDEX IF NOT EXISTS idx_news_asset_id ON news_articles(asset_id);",
            "CREATE INDEX IF NOT EXISTS idx_news_keywords ON news_articles(keywords);",
            
            # Prediction evaluations indexes
            "CREATE INDEX IF NOT EXISTS idx_evaluations_prediction ON prediction_evaluations(prediction_id);",
            "CREATE INDEX IF NOT EXISTS idx_evaluations_created_at ON prediction_evaluations(created_at DESC);",
        ]
        
        # Filter indexes based on database type
        database_url = str(self.engine.url)
        if database_url.startswith('sqlite'):
            # SQLite doesn't support partial indexes or some advanced features
            indexes = [idx for idx in indexes if "IF NOT EXISTS" in idx]
        
        success_count = 0
        with self.engine.connect() as conn:
            for index_sql in indexes:
                try:
                    conn.execute(index_sql)
                    success_count += 1
                    self.logger.debug(f"Created index: {index_sql[:50]}...")
                except Exception as e:
                    self.logger.warning(f"Failed to create index: {e}")
        
        self.logger.info(f"Created {success_count}/{len(indexes)} performance indexes")
        return success_count
    
    def analyze_query_performance(self, query: str) -> dict:
        """Analyze query performance and suggest optimizations."""
        try:
            with self.engine.connect() as conn:
                # Explain query
                explain_result = conn.execute(f"EXPLAIN {query}").fetchall()
                
                return {
                    "query": query,
                    "explain_plan": [dict(row) for row in explain_result],
                    "suggestions": self._generate_optimization_suggestions(explain_result),
                }
        except Exception as e:
            self.logger.error(f"Failed to analyze query: {e}")
            return {"error": str(e)}
    
    def _generate_optimization_suggestions(self, explain_result) -> list:
        """Generate optimization suggestions based on explain plan."""
        suggestions = []
        
        for row in explain_result:
            plan = str(row).lower()
            
            if "full scan" in plan:
                suggestions.append("Consider adding an index to avoid full table scan")
            
            if "sequential scan" in plan:
                suggestions.append("Sequential scan detected - index might improve performance")
            
            if "sort" in plan:
                suggestions.append("Consider adding an index to avoid expensive sort operation")
        
        return suggestions


# Global database manager instance
db_manager: Optional[DatabaseManager] = None


def init_database(config: Config) -> DatabaseManager:
    """Initialize database manager."""
    global db_manager
    
    db_manager = DatabaseManager(config)
    db_manager.initialize_database()
    db_manager.create_engine_with_pooling()
    db_manager.create_session_factory()
    
    return db_manager


def get_db_manager() -> Optional[DatabaseManager]:
    """Get global database manager."""
    return db_manager


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Get database session from global manager."""
    if db_manager is None:
        raise RuntimeError("Database manager not initialized")
    
    with db_manager.get_session() as session:
        yield session


# Database health check
def check_database_health() -> dict:
    """Check database health."""
    if db_manager is None:
        return {"status": "not_initialized"}
    
    return db_manager.health_check()
