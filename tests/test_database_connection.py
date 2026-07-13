import pytest

from src.database.connection import create_engine_instance, get_database_url


def test_env_postgresql_url_is_accepted(monkeypatch):
    url = "postgresql+psycopg2://user:password@database/app"
    monkeypatch.setenv("DATABASE_URL", url)
    assert get_database_url() == url


def test_env_sqlite_url_is_rejected(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///production.db")
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        get_database_url()


def test_explicit_sqlite_engine_is_accepted():
    engine = create_engine_instance("sqlite:///:memory:")
    try:
        assert engine.dialect.name == "sqlite"
    finally:
        engine.dispose()
