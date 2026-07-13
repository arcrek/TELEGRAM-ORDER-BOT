"""
Database connection setup.
"""

import os
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session
from src.database.models.base import Base

# Module-level singletons — one engine, one pool, shared across all requests/handlers.
_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_database_url() -> str:
    """Get database URL for PostgreSQL.

    Priority:
    1. DATABASE_URL (explicit, should point to PostgreSQL)
    2. DB_* PostgreSQL settings (if DATABASE_URL not set)
    """
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        if not database_url.startswith(("postgresql://", "postgresql+")):
            raise RuntimeError("DATABASE_URL must use PostgreSQL")
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


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def create_engine_instance(database_url: str | None = None) -> Engine:
    """Create SQLAlchemy engine. Call once; reuse the returned instance."""
    if database_url is None:
        database_url = get_database_url()

    if _is_sqlite(database_url):
        # SQLite: no pool tuning needed; used only in tests
        return create_engine(
            database_url, echo=False, connect_args={"check_same_thread": False}
        )

    return create_engine(
        database_url,
        echo=False,
        pool_size=10,  # persistent connections kept open
        max_overflow=20,  # extra connections allowed under burst
        pool_recycle=1800,  # recycle connections older than 30 min (avoids stale TCP)
        pool_pre_ping=True,  # test connection health before use
        pool_timeout=30,  # raise after 30 s if no connection available
    )


def get_engine() -> Engine:
    """Return the module-level singleton engine, creating it on first call."""
    global _engine
    if _engine is None:
        _engine = create_engine_instance()
    return _engine


def get_session_factory(engine: Engine | None = None) -> sessionmaker:
    """Return the module-level singleton session factory.

    Pass `engine` only when you need an isolated factory (e.g. tests).
    All production code should omit the argument so the singleton is reused.
    """
    global _SessionLocal
    if engine is not None:
        # Caller supplied an explicit engine (test isolation) — don't cache it.
        return sessionmaker(bind=engine, autocommit=False, autoflush=False)
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autocommit=False, autoflush=False
        )
    return _SessionLocal


def init_database(engine: Engine | None = None) -> None:
    """Create all tables. Uses the singleton engine unless one is supplied."""
    Base.metadata.create_all(engine or get_engine())


def get_db_session():
    """FastAPI/Flask dependency — yields a session and always closes it."""
    session: Session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
