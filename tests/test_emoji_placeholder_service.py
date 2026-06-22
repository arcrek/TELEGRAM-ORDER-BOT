import json

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


from src.database.services.emoji_placeholder_service import EmojiPlaceholderService


def test_create_and_get():
    session = _session()
    svc = EmojiPlaceholderService(session)
    pid = svc.create("Header")
    assert isinstance(pid, int)
    row = svc.get(pid)
    assert row.name == "Header"
    assert row.content is None


def test_set_content_stores_json_and_renders():
    session = _session()
    svc = EmojiPlaceholderService(session)
    pid = svc.create("Banner")
    units = [
        {"t": "emoji", "id": "5368324170671202286", "fb": "🔔"},
        {"t": "text", "v": "THÔNG BÁO"},
    ]
    svc.set_content(pid, units, raw_text="🔔THÔNG BÁO", set_by=42)
    row = svc.get(pid)
    assert json.loads(row.content) == units
    assert row.set_by == 42
    html = svc.get_rendered_html(pid)
    assert html == '<tg-emoji emoji-id="5368324170671202286">🔔</tg-emoji>THÔNG BÁO'


def test_units_to_html_escapes_text_units():
    html = EmojiPlaceholderService.units_to_html([{"t": "text", "v": "a < b & c"}])
    assert html == "a &lt; b &amp; c"


def test_get_rendered_html_missing_or_empty_returns_blank():
    session = _session()
    svc = EmojiPlaceholderService(session)
    assert svc.get_rendered_html(999) == ""
    pid = svc.create("Empty")
    assert svc.get_rendered_html(pid) == ""


def test_render_reflects_updated_content():
    session = _session()
    svc = EmojiPlaceholderService(session)
    pid = svc.create("X")
    svc.set_content(pid, [{"t": "text", "v": "one"}], raw_text="one", set_by=None)
    assert svc.get_rendered_html(pid) == "one"
    svc.set_content(pid, [{"t": "text", "v": "two"}], raw_text="two", set_by=None)
    assert svc.get_rendered_html(pid) == "two"


def test_delete_removes():
    session = _session()
    svc = EmojiPlaceholderService(session)
    pid = svc.create("Y")
    svc.set_content(pid, [{"t": "text", "v": "hi"}], raw_text="hi", set_by=None)
    assert svc.get_rendered_html(pid) == "hi"
    assert svc.delete(pid) is True
    assert svc.get_rendered_html(pid) == ""
