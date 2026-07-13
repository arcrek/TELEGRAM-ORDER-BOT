"""
Unit tests for AppSettingsService.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.base import Base
from src.database.services.app_settings_service import AppSettingsService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestAppSettingsServiceDefaults:
    def test_get_settings_creates_singleton(self, db_session):
        service = AppSettingsService(db_session)
        settings = service.get_settings()
        assert settings is not None
        assert settings.id == "global"

    def test_default_timezone_is_ho_chi_minh(self, db_session):
        service = AppSettingsService(db_session)
        settings = service.get_settings()
        assert settings.timezone == "Asia/Ho_Chi_Minh"

    def test_model_default_is_the_only_initial_timezone_source(
        self, db_session, monkeypatch
    ):
        monkeypatch.setenv("APP_TIMEZONE", "America/New_York")
        service = AppSettingsService(db_session)
        settings = service.get_settings()
        assert settings.timezone == "Asia/Ho_Chi_Minh"

    def test_singleton_not_recreated_on_second_call(self, db_session):
        """Second call returns same row, no duplicate creation."""
        service = AppSettingsService(db_session)
        s1 = service.get_settings()
        s2 = service.get_settings()
        assert s1.id == s2.id


class TestAppSettingsServiceUpdate:
    def test_update_valid_timezone(self, db_session):
        service = AppSettingsService(db_session)
        service.get_settings()  # ensure row exists
        updated = service.update_settings(timezone="Europe/Berlin")
        assert updated.timezone == "Europe/Berlin"

    def test_update_persists_across_calls(self, db_session):
        service = AppSettingsService(db_session)
        service.update_settings(timezone="Europe/London")
        fetched = service.get_settings()
        assert fetched.timezone == "Europe/London"

    def test_update_invalid_timezone_raises_value_error(self, db_session):
        service = AppSettingsService(db_session)
        with pytest.raises(ValueError, match="Invalid IANA timezone"):
            service.update_settings(timezone="Fake/City")

    def test_update_utc_accepted(self, db_session):
        service = AppSettingsService(db_session)
        updated = service.update_settings(timezone="UTC")
        assert updated.timezone == "UTC"

    def test_update_can_flush_without_committing(self, db_session):
        service = AppSettingsService(db_session)
        service.get_settings()
        service.update_settings(timezone="UTC", commit=False)
        db_session.rollback()
        assert service.get_settings().timezone == "Asia/Ho_Chi_Minh"


def test_default_identity_values_are_generic(db_session):
    settings = AppSettingsService(db_session).get_settings()
    assert settings.system_name == "Bot Order System"
    assert settings.bot_url == ""
    assert settings.support_line_1 == ""
    assert settings.support_line_2 == ""
    assert settings.order_prefix == "ORD"
    assert settings.api_docs_url == ""


def test_update_normalizes_identity_values(db_session):
    updated = AppSettingsService(db_session).update_settings(
        system_name="  Example Shop  ",
        bot_url="https://t.me/example_shop_bot",
        support_line_1=" @support ",
        support_line_2=" ",
        timezone="UTC",
        order_prefix="abc",
        api_docs_url="https://shop.example/api",
    )
    assert updated.system_name == "Example Shop"
    assert updated.order_prefix == "ABC"
    assert updated.support_line_1 == "@support"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("system_name", "", "system_name"),
        ("bot_url", "http://t.me/example_shop_bot", "bot_url"),
        ("bot_url", "https://example.com/bot", "bot_url"),
        ("order_prefix", "TUX", "cannot start with TU"),
        ("order_prefix", "A-1", "order_prefix"),
        ("api_docs_url", "http://shop.example/api", "api_docs_url"),
        ("support_line_1", "x" * 201, "support_line_1"),
    ],
)
def test_invalid_identity_value_fails(db_session, field, value, message):
    service = AppSettingsService(db_session)
    valid = {
        "system_name": "Example Shop",
        "bot_url": "https://t.me/example_shop_bot",
        "support_line_1": "Support",
        "support_line_2": "",
        "timezone": "UTC",
        "order_prefix": "ORD",
        "api_docs_url": "https://shop.example/api",
    }
    valid[field] = value
    with pytest.raises(ValueError, match=message):
        service.update_settings(**valid)
