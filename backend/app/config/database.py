"""
Database configuration for different environments.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://username:password@localhost/sentinel_trading'
)

# For development with SQLite
if os.getenv('FLASK_ENV') == 'development' and not os.getenv('DATABASE_URL'):
    DATABASE_URL = 'sqlite:///sentinel_trading.db'

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=os.getenv('SQL_DEBUG', 'False').lower() == 'true'
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise
