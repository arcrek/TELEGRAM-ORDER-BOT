"""Tests for BlockService."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.base import Base
from src.database.services.block_service import BlockService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def svc(db_session):
    return BlockService(db_session)


def test_parse_identifier_numeric():
    assert BlockService.parse_identifier("123456") == (123456, None)


def test_parse_identifier_username_with_at():
    assert BlockService.parse_identifier("@Alice") == (None, "alice")


def test_parse_identifier_username_bare():
    assert BlockService.parse_identifier("Bob") == (None, "bob")


def test_parse_identifier_empty_raises():
    with pytest.raises(ValueError):
        BlockService.parse_identifier("   ")


def test_block_by_id_then_is_blocked(svc):
    svc.block("777")
    assert svc.is_blocked(777, None) is True
    assert svc.is_blocked(778, None) is False


def test_block_by_username_matches_case_insensitively(svc):
    svc.block("@Carol")
    assert svc.is_blocked(None, "carol") is True
    assert svc.is_blocked(None, "@CAROL") is True
    assert svc.is_blocked(999, None) is False


def test_is_blocked_matches_on_either_key(svc):
    svc.block("dave")  # username-only row
    # User whose id is unknown to us but username matches → blocked.
    assert svc.is_blocked(12345, "dave") is True


def test_is_blocked_false_when_no_identifiers(svc):
    assert svc.is_blocked(None, None) is False


def test_block_is_idempotent(svc):
    a = svc.block("555")
    b = svc.block("555")
    assert a.id == b.id
    _items, total = svc.list_blocked()
    assert total == 1


def test_unblock_by_id(svc):
    svc.block("321")
    assert svc.unblock("321") is True
    assert svc.is_blocked(321, None) is False
    assert svc.unblock("321") is False  # already gone


def test_unblock_by_username(svc):
    svc.block("@erin")
    assert svc.unblock("Erin") is True
    assert svc.is_blocked(None, "erin") is False


def test_add_block_requires_an_identifier(svc):
    with pytest.raises(ValueError):
        svc.add_block()


def test_remove_block_by_id(svc):
    row = svc.block("404")
    assert svc.remove_block(row.id) is True
    assert svc.remove_block(row.id) is False


def test_list_blocked_search_and_pagination(svc):
    svc.block("100")
    svc.block("@frank")
    svc.block("@grace")
    items, total = svc.list_blocked(search="fra")
    assert total == 1
    assert items[0].username == "frank"
    items, total = svc.list_blocked()
    assert total == 3
