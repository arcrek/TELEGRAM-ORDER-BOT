from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.dashboard.auth import get_db, require_admin_role, require_viewer_or_admin
from src.dashboard.main import app
from src.database.models.base import Base


def test_public_settings_exposes_only_system_name(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'settings.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def db_override():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = db_override
    try:
        response = TestClient(app).get("/api/app-settings/public")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"system_name": "Bot Order System"}


def test_admin_can_replace_all_settings(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'settings.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def db_override():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[require_admin_role] = lambda: object()
    app.dependency_overrides[require_viewer_or_admin] = lambda: object()
    payload = {
        "system_name": "Example Shop",
        "bot_url": "https://t.me/example_shop_bot",
        "support_line_1": "@support",
        "support_line_2": "",
        "timezone": "UTC",
        "order_prefix": "SHOP",
        "api_docs_url": "https://shop.example/api",
    }
    try:
        response = TestClient(app).put("/api/app-settings", json=payload)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == payload
