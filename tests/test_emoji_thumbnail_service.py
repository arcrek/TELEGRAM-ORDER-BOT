from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.base import Base
from src.database.models.emoji_thumbnail import EmojiThumbnail
from src.database.services.emoji_thumbnail_service import (
    EmojiThumbnailService,
    THUMBNAIL_NEGATIVE_TTL,
)
from src.database.services.emoji_placeholder_service import EmojiPlaceholderService


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_model_stores_bytes():
    session = _session()
    row = EmojiThumbnail(custom_emoji_id="111", data=b"\x89PNG", mime="image/webp")
    session.add(row)
    session.commit()
    fetched = session.get(EmojiThumbnail, "111")
    assert fetched.data == b"\x89PNG"
    assert fetched.mime == "image/webp"
    assert fetched.fetched_at is not None


def test_store_and_get():
    session = _session()
    svc = EmojiThumbnailService(session)
    svc.store("111", b"img", "image/webp")
    row = svc.get("111")
    assert row.data == b"img"
    assert row.mime == "image/webp"


def test_store_failure_creates_null_row():
    session = _session()
    svc = EmojiThumbnailService(session)
    row = svc.store_failure("222")
    assert row.data is None
    assert svc.get("222") is not None


def test_is_stale_failure_boundary():
    # data present -> never stale
    present = EmojiThumbnail(custom_emoji_id="a", data=b"x", fetched_at=datetime.now(timezone.utc))
    assert EmojiThumbnailService.is_stale_failure(present) is False
    # fresh failure -> not stale
    fresh = EmojiThumbnail(custom_emoji_id="b", data=None, fetched_at=datetime.now(timezone.utc))
    assert EmojiThumbnailService.is_stale_failure(fresh) is False
    # old failure -> stale
    old = EmojiThumbnail(
        custom_emoji_id="c",
        data=None,
        fetched_at=datetime.now(timezone.utc) - THUMBNAIL_NEGATIVE_TTL - timedelta(minutes=1),
    )
    assert EmojiThumbnailService.is_stale_failure(old) is True


def test_referenced_emoji_ids():
    session = _session()
    psvc = EmojiPlaceholderService(session)
    pid = psvc.create("P")
    psvc.set_content(
        pid,
        [{"t": "emoji", "id": "111", "fb": "🔔"}, {"t": "text", "v": "hi"},
         {"t": "emoji", "id": "222", "fb": "🔥"}],
        raw_text="🔔hi🔥",
        set_by=None,
    )
    # An unconfigured placeholder contributes nothing.
    psvc.create("empty")
    assert psvc.referenced_emoji_ids() == {"111", "222"}
