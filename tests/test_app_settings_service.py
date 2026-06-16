"""
Unit tests for AppSettingsService.
"""

import os
import pytest
from unittest.mock import patch
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
        """When APP_TIMEZONE env var is absent, default to Asia/Ho_Chi_Minh."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("APP_TIMEZONE", None)
            service = AppSettingsService(db_session)
            settings = service.get_settings()
        assert settings.timezone == "Asia/Ho_Chi_Minh"

    def test_seed_from_env_variable(self, db_session):
        """APP_TIMEZONE seeds the singleton timezone on first creation."""
        with patch.dict(os.environ, {"APP_TIMEZONE": "America/New_York"}):
            service = AppSettingsService(db_session)
            settings = service.get_settings()
        assert settings.timezone == "America/New_York"

    def test_invalid_env_variable_falls_back_to_default(self, db_session):
        """An invalid APP_TIMEZONE triggers a warning and falls back."""
        with patch.dict(os.environ, {"APP_TIMEZONE": "Not/A/Timezone"}):
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
