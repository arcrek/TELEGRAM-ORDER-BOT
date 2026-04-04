"""
Tests for BotUiSettingsService.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.base import Base
from src.database.services.bot_ui_settings_service import BotUiSettingsService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_get_settings_creates_singleton_row(db_session):
    service = BotUiSettingsService(db_session)
    settings = service.get_settings()

    assert settings is not None
    assert settings.id == "global"
    assert settings.product_choose_text is None
    assert settings.variation_choose_text is None


def test_update_settings_trims_and_normalizes_empty(db_session):
    service = BotUiSettingsService(db_session)

    settings = service.update_settings(
        product_choose_text="  Choose product  ",
        variation_choose_text="   ",
    )

    assert settings.product_choose_text == "Choose product"
    assert settings.variation_choose_text is None

