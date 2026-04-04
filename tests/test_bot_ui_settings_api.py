"""
Tests for bot UI settings API endpoints.
"""
import pytest
import os
import tempfile
import atexit
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.dashboard.main import app
from src.database.models import Admin, AdminRole
from src.database.models.base import Base
from src.dashboard.auth import get_password_hash, create_access_token, get_db


test_db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
test_db_path = test_db_file.name
test_db_file.close()


def cleanup_test_db():
    try:
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)
    except Exception:
        pass


atexit.register(cleanup_test_db)

test_engine = create_engine(
    f"sqlite:///{test_db_path}",
    echo=False,
    connect_args={"check_same_thread": False},
)
Base.metadata.create_all(test_engine)
TestSession = sessionmaker(bind=test_engine)


def override_get_db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    os.environ["DASHBOARD_SECRET_KEY"] = "test-secret-key"
    import src.dashboard.auth as auth_module
    auth_module.SECRET_KEY = "test-secret-key"
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True, scope="function")
def setup_database():
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield


@pytest.fixture
def test_db():
    session = TestSession()
    yield session
    session.close()


@pytest.fixture
def auth_token(test_db: Session):
    admin = Admin(
        id="admin_1",
        username="testadmin",
        email="test@example.com",
        password_hash=get_password_hash("testpass123"),
        full_name="Test Admin",
        role=AdminRole.ADMIN,
        is_active=True,
    )
    test_db.add(admin)
    test_db.commit()
    return create_access_token(data={"sub": admin.username})


def test_get_bot_ui_settings_requires_auth(client):
    response = client.get("/api/bot-ui-settings")
    assert response.status_code == 401


def test_get_bot_ui_settings_success(client, auth_token):
    response = client.get(
        "/api/bot-ui-settings",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "product_choose_text" in data
    assert "variation_choose_text" in data
    assert "webapp_button_text" in data
    assert "webapp_url" in data


def test_put_bot_ui_settings_success(client, auth_token):
    response = client.put(
        "/api/bot-ui-settings",
        json={
            "product_choose_text": "Choose category",
            "variation_choose_text": "Choose package",
            "webapp_button_text": "Open App",
            "webapp_url": "https://example.com/app",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["product_choose_text"] == "Choose category"
    assert data["variation_choose_text"] == "Choose package"
    assert data["webapp_button_text"] == "Open App"
    assert data["webapp_url"] == "https://example.com/app"

    check = client.get(
        "/api/bot-ui-settings",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert check.status_code == 200
    check_data = check.json()
    assert check_data["product_choose_text"] == "Choose category"
    assert check_data["variation_choose_text"] == "Choose package"
    assert check_data["webapp_button_text"] == "Open App"
    assert check_data["webapp_url"] == "https://example.com/app"

