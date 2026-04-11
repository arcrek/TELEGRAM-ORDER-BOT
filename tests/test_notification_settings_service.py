"""
Tests for NotificationSettingsService.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.base import Base
from src.database.services.notification_settings_service import NotificationSettingsService


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_get_settings_creates_singleton_row(db_session):
    service = NotificationSettingsService(db_session)
    settings = service.get_settings()
    assert settings is not None
    assert settings.id == "global"
    assert settings.order_notify_enabled is False
    assert service.get_whitelist_chat_ids(settings) == []

    # Second call should return same row
    settings2 = service.get_settings()
    assert settings2.id == "global"


def test_update_settings_normalizes_whitelist(db_session):
    service = NotificationSettingsService(db_session)

    settings = service.update_settings(
        order_notify_enabled=True,
        order_notify_on_created=True,
        order_notify_on_paid=False,
        whitelist_chat_ids=[123, "123", -1001, "bad", 0, 123, "-1001:5", "-1001:5", "-1001:0"],
    )

    assert settings.order_notify_enabled is True
    assert settings.order_notify_on_created is True
    assert settings.order_notify_on_paid is False

    whitelist = service.get_whitelist_chat_ids(settings)
    assert whitelist == [123, -1001, 0]

    entries = service.get_whitelist_entries(settings)
    assert entries == ["123", "-1001", "0", "-1001:5"]

