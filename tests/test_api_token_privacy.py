"""
Regression tests for customer API token privacy ([CRIT-03]).

Verifies that:
1. `GET /api/balances` user list does not include `api_token` in serialized rows.
2. `GET /api/balances` returns boolean flag `has_api_token: True|False`.
3. `GET /api/balances/{bot_user_id}` detail summary does not expose `api_token` in user payload.
4. Plaintext customer API tokens are never leaked in batch/detail queries.
5. `POST /api/balances/{bot_user_id}/api-token` generates and returns token only on explicit invocation.
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.dashboard.auth import create_access_token, get_db
from src.dashboard.main import app
from src.database.models import Admin, AdminRole, BotUser
from src.database.models.base import Base


@pytest.fixture
def test_setup():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    with testing_session() as db:
        admin = Admin(
            id="admin_token_test",
            username="admin_tester",
            password_hash="fake_hash",
            full_name="Admin Tester",
            role=AdminRole.ADMIN,
            is_active=True,
        )
        db.add(admin)

        user_with_token = BotUser(
            id="user_token_yes",
            telegram_user_id=400001,
            username="user_with_token",
            balance=50_000,
            api_token="secret_token_abc123xyz789",
        )
        user_without_token = BotUser(
            id="user_token_no",
            telegram_user_id=400002,
            username="user_without_token",
            balance=10_000,
            api_token=None,
        )
        db.add_all([user_with_token, user_without_token])
        db.commit()

    def override_get_db():
        with testing_session() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    token = create_access_token(
        data={"sub": "admin_tester", "role": "admin", "admin_id": "admin_token_test"},
        expires_delta=timedelta(minutes=30),
    )
    headers = {"Authorization": f"Bearer {token}"}

    try:
        yield TestClient(app), headers
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_list_balances_does_not_expose_api_tokens(test_setup):
    client, headers = test_setup

    response = client.get("/api/balances", headers=headers)
    assert response.status_code == 200

    raw_text = response.text
    # Absolute privacy: Plaintext secret token must NOT exist anywhere in the HTTP response
    assert "secret_token_abc123xyz789" not in raw_text

    data = response.json()
    items = data["items"]
    assert len(items) == 2

    # Map items by id
    item_map = {item["bot_user_id"]: item for item in items}

    # Verify user with token
    user_yes = item_map["user_token_yes"]
    assert "api_token" not in user_yes
    assert user_yes["has_api_token"] is True

    # Verify user without token
    user_no = item_map["user_token_no"]
    assert "api_token" not in user_no
    assert user_no["has_api_token"] is False


def test_get_balance_detail_does_not_expose_api_token(test_setup):
    client, headers = test_setup

    response = client.get("/api/balances/user_token_yes", headers=headers)
    assert response.status_code == 200

    raw_text = response.text
    assert "secret_token_abc123xyz789" not in raw_text

    data = response.json()
    user = data["user"]
    assert "api_token" not in user
    assert user["has_api_token"] is True


def test_generate_api_token_endpoint(test_setup):
    client, headers = test_setup

    # Generate token for user_token_no
    response = client.post("/api/balances/user_token_no/api-token", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["bot_user_id"] == "user_token_no"
    new_token = data["api_token"]
    assert new_token is not None and len(new_token) > 0

    # Subsequent detail check must have has_api_token: True but not expose plaintext token
    detail_res = client.get("/api/balances/user_token_no", headers=headers)
    assert detail_res.status_code == 200
    user_detail = detail_res.json()["user"]
    assert user_detail["has_api_token"] is True
    assert "api_token" not in user_detail
