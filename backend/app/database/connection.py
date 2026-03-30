"""
Database connection for Supabase PostgreSQL.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging

logger = logging.getLogger(__name__)

class DatabaseConnection:
    """Database connection manager for Supabase."""
    
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        self.engine = None
        self.SessionLocal = None
        self.Base = declarative_base()
        
    def connect(self):
        """Initialize database connection."""
        try:
            if not self.database_url:
                raise ValueError("DATABASE_URL environment variable is not set")
            
            # Create SQLAlchemy engine
            self.engine = create_engine(
                self.database_url,
                echo=os.getenv('SQL_DEBUG', 'False').lower() == 'true',
                pool_pre_ping=True,
                pool_recycle=300
            )
            
            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            logger.info("Database connection established successfully")
            
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            raise
    
    def get_session(self):
        """Get database session."""
        if not self.SessionLocal:
            self.connect()
        return self.SessionLocal()
    
    def execute_raw_sql(self, query: str, params: dict = None):
        """Execute raw SQL query."""
        try:
            with self.engine.connect() as connection:
                result = connection.execute(query, params or {})
                return result.fetchall()
        except Exception as e:
            logger.error(f"Error executing SQL query: {e}")
            raise
    
    def test_connection(self):
        """Test database connection."""
        try:
            with self.engine.connect() as connection:
                result = connection.execute("SELECT 1 as test")
                return result.fetchone()[0] == 1
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def create_tables(self):
        """Create all tables from models."""
        try:
            self.Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            raise
    
    def close(self):
        """Close database connection."""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection closed")

# Global database instance
db = DatabaseConnection()

def get_db():
    """Get database session."""
    session = db.get_session()
    try:
        yield session
    finally:
        session.close()

def init_db():
    """Initialize database."""
    db.connect()
    db.create_tables()

def test_db_connection():
    """Test database connection."""
    return db.test_connection()
