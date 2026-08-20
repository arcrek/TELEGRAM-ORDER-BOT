"""Tests for the blocked-users dashboard router."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.dashboard.auth import get_db, require_admin_role, require_viewer_or_admin
from src.dashboard.main import app
from src.database.models.base import Base


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    # Bypass auth in tests.
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin_role] = lambda: object()
    app.dependency_overrides[require_viewer_or_admin] = lambda: object()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_add_list_and_delete_block(client):
    # Add by id.
    r = client.post("/api/blocked-users", json={"identifier": "12345"})
    assert r.status_code == 200, r.text
    block_id = r.json()["id"]
    assert r.json()["telegram_user_id"] == 12345

    # Add by username.
    r2 = client.post("/api/blocked-users", json={"identifier": "@SomeUser"})
    assert r2.status_code == 200
    assert r2.json()["username"] == "someuser"

    # List shows both.
    r3 = client.get("/api/blocked-users")
    assert r3.status_code == 200
    assert r3.json()["total"] == 2

    # Search by username substring.
    r4 = client.get("/api/blocked-users", params={"search": "some"})
    assert r4.json()["total"] == 1

    # Delete the first.
    r5 = client.delete(f"/api/blocked-users/{block_id}")
    assert r5.status_code == 200
    assert r5.json()["success"] is True

    # Deleting again → 404.
    r6 = client.delete(f"/api/blocked-users/{block_id}")
    assert r6.status_code == 404


def test_add_block_empty_identifier_returns_400(client):
    r = client.post("/api/blocked-users", json={"identifier": "   "})
    assert r.status_code == 400
