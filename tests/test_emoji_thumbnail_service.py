from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.base import Base
from src.database.models.emoji_thumbnail import EmojiThumbnail


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
