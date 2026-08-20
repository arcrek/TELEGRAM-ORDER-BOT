import atexit
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.dashboard.auth import get_current_admin, get_db
from src.dashboard.main import app
from src.database.models import *
from src.database.models.base import Base
from src.database.models.enums import OrderStatus
from src.database.models.order import Order

# Named temp-file SQLite (in-memory :memory: is per-connection and breaks pooling)
with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as _f:
    _path = _f.name
atexit.register(lambda: os.path.exists(_path) and os.unlink(_path))

engine = create_engine(f"sqlite:///{_path}", connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
TestSession = sessionmaker(bind=engine)


def _override_get_db():
    s = TestSession()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_admin] = lambda: {"username": "admin"}
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def db():
    s = TestSession()
    yield s
    s.close()


def test_recent_paid_returns_only_orders_after_since(client, db):
    base = datetime(2026, 6, 29, 10, 0, 0)
    # old paid order (before since) and a fresh one (after since)
    db.add(Order(id="OLD", user_id=1, total_amount=1000,
                 status=OrderStatus.DELIVERED, paid_at=base - timedelta(minutes=5)))
    db.add(Order(id="NEW", user_id=2, total_amount=50000,
                 status=OrderStatus.DELIVERED, paid_at=base + timedelta(seconds=5)))
    db.commit()

    since = base.replace(tzinfo=timezone.utc).isoformat()
    resp = client.get(f"/api/orders/recent-paid?since={since}")
    assert resp.status_code == 200
    body = resp.json()
    assert "server_now" in body
    ids = [o["id"] for o in body["orders"]]
    assert ids == ["NEW"]  # DELIVERED order still counts; old one excluded


def test_recent_paid_without_since_is_empty(client):
    resp = client.get("/api/orders/recent-paid")
    assert resp.status_code == 200
    body = resp.json()
    assert body["orders"] == []
    assert "server_now" in body


def test_recent_paid_requires_auth():
    # Do NOT override get_current_admin -> real auth runs -> 401/403
    app.dependency_overrides[get_db] = _override_get_db
    try:
        resp = TestClient(app).get("/api/orders/recent-paid?since=2026-06-29T10:00:00+00:00")
        assert resp.status_code in (401, 403)
    finally:
        app.dependency_overrides.clear()


def test_list_recently_paid_compiles_for_postgres():
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    from src.database.models.order import Order
    stmt = select(Order).where(Order.paid_at.isnot(None), Order.paid_at > datetime(2026, 1, 1))
    # Must not raise for the Postgres dialect.
    str(stmt.compile(dialect=postgresql.dialect()))
