"""Tests for the BlockedUser model and its partial unique indexes."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.database.models.base import Base
from src.database.models.blocked_users import BlockedUser


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_block_by_id_and_by_username_coexist(db_session):
    db_session.add(BlockedUser(telegram_user_id=111))
    db_session.add(BlockedUser(username="alice"))
    db_session.commit()
    assert db_session.query(BlockedUser).count() == 2


def test_duplicate_telegram_id_violates_partial_unique(db_session):
    db_session.add(BlockedUser(telegram_user_id=222))
    db_session.commit()
    db_session.add(BlockedUser(telegram_user_id=222))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_duplicate_username_violates_partial_unique(db_session):
    db_session.add(BlockedUser(username="bob"))
    db_session.commit()
    db_session.add(BlockedUser(username="bob"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_multiple_username_only_rows_do_not_collide_on_id_index(db_session):
    # Both have telegram_user_id = NULL; the partial index excludes NULLs.
    db_session.add(BlockedUser(username="carol"))
    db_session.add(BlockedUser(username="dave"))
    db_session.commit()
    assert db_session.query(BlockedUser).count() == 2
