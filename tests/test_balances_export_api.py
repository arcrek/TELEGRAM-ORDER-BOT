"""Tests for the active-user balance CSV export."""

import csv
import io

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
def export_client(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    with testing_session() as db:
        db.add(
            Admin(
                id="admin-1",
                username="admin",
                password_hash="unused",
                full_name="Admin",
                role=AdminRole.ADMIN,
                is_active=True,
            )
        )
        db.add_all(
            [
                BotUser(
                    id="active",
                    telegram_user_id=1001,
                    username="active_user",
                    first_name="Nguyễn Văn",
                    last_name="An",
                    has_started=True,
                    is_active=True,
                    balance=125000,
                ),
                BotUser(
                    id="inactive",
                    telegram_user_id=1002,
                    username="inactive_user",
                    has_started=True,
                    is_active=False,
                    balance=500,
                ),
                BotUser(
                    id="not-started",
                    telegram_user_id=1003,
                    username="not_started_user",
                    has_started=False,
                    is_active=True,
                    balance=900,
                ),
            ]
        )
        db.commit()

    def override_get_db():
        with testing_session() as db:
            yield db

    monkeypatch.setenv("DASHBOARD_SECRET_KEY", "test-export-secret")
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app), create_access_token({"sub": "admin"})
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_export_active_users_csv(export_client):
    client, token = export_client

    assert client.get("/api/balances/export").status_code == 401

    response = client.get(
        "/api/balances/export",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.text.startswith("\ufeff")
    assert list(csv.reader(io.StringIO(response.text.removeprefix("\ufeff")))) == [
        ["Username", "Name", "Telegram ID", "Balance"],
        ["active_user", "Nguyễn Văn An", "1001", "125000"],
    ]
