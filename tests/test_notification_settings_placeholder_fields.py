from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.base import Base
from src.database.services.notification_settings_service import (
    NotificationSettingsService,
)


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_update_persists_placeholder_ids():
    session = _session()
    svc = NotificationSettingsService(session)
    settings = svc.update_settings(
        order_notify_enabled=True,
        order_notify_on_created=False,
        order_notify_on_paid=True,
        topup_notify_on_paid=False,
        whitelist_chat_ids=[],
        upgrade_chat_ids=[],
        topup_chat_ids=[],
        header_placeholder_id=3,
        footer_placeholder_id=None,
    )
    assert settings.header_placeholder_id == 3
    assert settings.footer_placeholder_id is None
