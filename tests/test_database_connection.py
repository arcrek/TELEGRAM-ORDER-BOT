import pytest
from sqlalchemy.engine import URL

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


def test_component_url_escapes_reserved_characters(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_USER", "user:name")
    monkeypatch.setenv("DB_PASSWORD", "p@ss/word?#")
    monkeypatch.setenv("DB_HOST", "2001:db8::1")
    monkeypatch.setenv("DB_PORT", "5433")
    monkeypatch.setenv("DB_NAME", "orders?archive")

    url = get_database_url()

    assert isinstance(url, URL)
    assert url.drivername == "postgresql+psycopg2"
    assert url.username == "user:name"
    assert url.password == "p@ss/word?#"
    assert url.host == "2001:db8::1"
    assert url.port == 5433
    assert url.database == "orders?archive"
    assert url.render_as_string(hide_password=False) == (
        "postgresql+psycopg2://user%3Aname:p%40ss%2Fword%3F%23"
        "@[2001:db8::1]:5433/orders?archive"
    )


def test_component_url_rejects_noninteger_port_without_leaking_password(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_USER", "user")
    monkeypatch.setenv("DB_PASSWORD", "do-not-leak")
    monkeypatch.setenv("DB_HOST", "postgres")
    monkeypatch.setenv("DB_PORT", "not-a-port")
    monkeypatch.setenv("DB_NAME", "orders")

    with pytest.raises(RuntimeError, match="DB_PORT must be an integer") as exc_info:
        get_database_url()

    assert "do-not-leak" not in str(exc_info.value)
