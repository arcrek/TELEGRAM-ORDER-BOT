"""A blocked user's API token cannot create an order (HTTP 403)."""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from src.database.models.base import Base
from src.database.models.bot_user import BotUser
from src.database.services.block_service import BlockService
from src.dashboard.main import app
from src.dashboard.auth import get_db


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

    # Seed a user with an API token, then block them.
    s = TestingSession()
    s.add(
        BotUser(
            telegram_user_id=700,
            username="apiuser",
            api_token="tok-123",
            has_started=True,
        )
    )
    s.commit()
    s.close()
    BlockService(TestingSession()).block("700")

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_blocked_user_order_returns_403(client):
    resp = client.post(
        "/api/v1/orders",
        headers={"Authorization": "Bearer tok-123"},
        json={"variation_id": "whatever", "quantity": 1},
    )
    assert resp.status_code == 403
