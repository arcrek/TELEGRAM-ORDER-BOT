from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.base import Base
from src.database.services.emoji_placeholder_service import EmojiPlaceholderService
from src.database.services.notification_settings_service import NotificationSettingsService
from src.database.services.order_notification_service import OrderNotificationService


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_compose_plain_when_no_header_footer():
    session = _session()
    svc = OrderNotificationService(session, bot=None)
    text, mode = svc._compose_with_emoji("hello")
    assert (text, mode) == ("hello", None)


def test_compose_wraps_header_and_footer():
    session = _session()
    emoji_svc = EmojiPlaceholderService(session)
    hid = emoji_svc.create("H")
    emoji_svc.set_content(hid, [{"t": "text", "v": "TOP"}], raw_text="TOP", set_by=None)
    fid = emoji_svc.create("F")
    emoji_svc.set_content(fid, [{"t": "text", "v": "BOT"}], raw_text="BOT", set_by=None)

    settings_svc = NotificationSettingsService(session)
    settings = settings_svc.get_settings()
    settings.header_placeholder_id = hid
    settings.footer_placeholder_id = fid
    session.commit()

    svc = OrderNotificationService(session, bot=None)
    text, mode = svc._compose_with_emoji("body")
    assert mode == "HTML"
    assert text == "TOP\nbody\nBOT"
