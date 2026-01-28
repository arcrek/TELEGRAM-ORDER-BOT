"""
Database connection setup.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from src.database.models.base import Base


def get_database_url() -> str:
    """Get database URL for PostgreSQL.

    Priority:
    1. DATABASE_URL (explicit, should point to PostgreSQL)
    2. DB_* PostgreSQL settings (if DATABASE_URL not set)
    """
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")

    if host and name and user and password:
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"

    raise RuntimeError(
        "Database configuration is missing. "
        "Set DATABASE_URL or DB_* environment variables for PostgreSQL."
    )


def create_engine_instance(database_url: str | None = None):
    """
    Create SQLAlchemy engine instance.
    
    Args:
        database_url: Database URL. If None, uses environment variable or default.
    
    Returns:
        Engine instance.
    """
    if database_url is None:
        database_url = get_database_url()

    engine = create_engine(database_url, echo=False)
    return engine


def get_session_factory(engine=None):
    """
    Get session factory.
    
    Args:
        engine: SQLAlchemy engine. If None, creates a new one.
    
    Returns:
        Session factory.
    """
    if engine is None:
        engine = create_engine_instance()
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_database(engine=None):
    """
    Initialize database tables.
    
    Args:
        engine: SQLAlchemy engine. If None, creates a new one.
    """
    if engine is None:
        engine = create_engine_instance()
    Base.metadata.create_all(engine)


def get_db_session(engine=None) -> Session:
    """
    Get database session (for dependency injection).
    
    Args:
        engine: SQLAlchemy engine. If None, creates a new one.
    
    Yields:
        Database session.
    """
    session_factory = get_session_factory(engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()

