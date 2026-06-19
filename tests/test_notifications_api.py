"""Tests for the consolidated multipart notifications /send endpoint."""
import io
import pytest
from unittest.mock import Mock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.dashboard.main import app
from src.dashboard.routers import notifications as notif_router
from src.database.models import Admin, AdminRole
from src.database.models.base import Base
from src.database.services.bot_user_service import BotUserService
from src.dashboard.auth import get_password_hash, create_access_token, get_db
from src.database.models import *  # noqa: F401,F403

import tempfile, os, atexit

test_db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
test_db_path = test_db_file.name
test_db_file.close()
atexit.register(lambda: os.path.exists(test_db_path) and os.unlink(test_db_path))

test_engine = create_engine(
    f"sqlite:///{test_db_path}", echo=False,
    connect_args={"check_same_thread": False}, pool_pre_ping=True,
)
Base.metadata.create_all(test_engine)
TestSession = sessionmaker(bind=test_engine)


def override_get_db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True, scope="function")
def setup_database():
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_token():
    session = TestSession()
    admin = Admin(
        id="admin_1", username="testadmin", email="a@b.com",
        password_hash=get_password_hash("x"), full_name="A",
        role=AdminRole.ADMIN, is_active=True,
    )
    session.add(admin)
    session.commit()
    session.close()
    return create_access_token(data={"sub": "testadmin"})


@pytest.fixture
def started_user():
    session = TestSession()
    BotUserService(session).track_user(telegram_user_id=111, username="u1")
    session.commit()
    session.close()


@pytest.fixture
def mock_bot(monkeypatch):
    bot = Mock()
    bot.send_message = Mock(return_value=Mock(message_id=1))
    bot.send_photo = Mock(return_value=Mock(photo=[Mock(file_id="FID")]))
    monkeypatch.setattr(notif_router, "get_bot_instance", lambda: bot)
    return bot


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_send_requires_auth(client):
    r = client.post("/api/notifications/send", data={"message": "hi"})
    assert r.status_code == 401


def test_send_rejects_empty_text_and_no_image(client, auth_token, mock_bot):
    r = client.post("/api/notifications/send",
                    data={"message": "  ", "audience": "all"}, headers=_auth(auth_token))
    assert r.status_code == 400


def test_send_rejects_bad_audience(client, auth_token, mock_bot):
    r = client.post("/api/notifications/send",
                    data={"message": "hi", "audience": "nobody"}, headers=_auth(auth_token))
    assert r.status_code == 400


def test_send_specific_requires_ids(client, auth_token, mock_bot):
    r = client.post("/api/notifications/send",
                    data={"message": "hi", "audience": "specific", "user_ids": ""},
                    headers=_auth(auth_token))
    assert r.status_code == 400


def test_send_rejects_non_image(client, auth_token, mock_bot):
    files = {"image": ("x.txt", io.BytesIO(b"hello"), "text/plain")}
    r = client.post("/api/notifications/send",
                    data={"message": "hi", "audience": "all"}, files=files,
                    headers=_auth(auth_token))
    assert r.status_code == 400


def test_send_rejects_oversized_image(client, auth_token, mock_bot):
    big = io.BytesIO(b"\x00" * (10 * 1024 * 1024 + 1))
    files = {"image": ("x.png", big, "image/png")}
    r = client.post("/api/notifications/send",
                    data={"message": "hi", "audience": "all"}, files=files,
                    headers=_auth(auth_token))
    assert r.status_code == 400


def test_send_text_only_all(client, auth_token, started_user, mock_bot):
    r = client.post("/api/notifications/send",
                    data={"message": "hello", "audience": "all"}, headers=_auth(auth_token))
    assert r.status_code == 200
    assert r.json()["total"] == 1
    mock_bot.send_message.assert_called_once_with(chat_id=111, text="hello")


def test_send_image_only_all(client, auth_token, started_user, mock_bot):
    files = {"image": ("x.png", io.BytesIO(b"PNG"), "image/png")}
    r = client.post("/api/notifications/send",
                    data={"message": "", "audience": "all"}, files=files,
                    headers=_auth(auth_token))
    assert r.status_code == 200
    assert mock_bot.send_photo.call_count == 1


def test_send_specific_dispatch(client, auth_token, started_user, mock_bot):
    r = client.post("/api/notifications/send",
                    data={"message": "hi", "audience": "specific", "user_ids": "111,222"},
                    headers=_auth(auth_token))
    assert r.status_code == 200
    assert r.json()["total"] == 2
