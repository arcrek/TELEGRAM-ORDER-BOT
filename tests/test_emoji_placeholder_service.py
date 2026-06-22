from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.base import Base
from src.database.models.emoji_placeholder import EmojiPlaceholder


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_model_table_creates_and_inserts():
    session = _session()
    row = EmojiPlaceholder(name="Header")
    session.add(row)
    session.commit()
    assert row.id is not None
    assert row.content is None
