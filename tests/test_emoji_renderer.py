from dataclasses import dataclass
from typing import Optional

from src.bot.messages.emoji_renderer import parse_emoji_units, render


@dataclass
class FakeEntity:
    type: str
    offset: int
    length: int
    custom_emoji_id: Optional[str] = None


def test_parse_emoji_only():
    # "🔔" is 1 code point but 2 UTF-16 code units (surrogate pair).
    text = "🔔"
    entities = [FakeEntity("custom_emoji", 0, 2, "111")]
    assert parse_emoji_units(text, entities) == [
        {"t": "emoji", "id": "111", "fb": "🔔"}
    ]


def test_parse_mixed_text_and_emoji():
    text = "🔔THÔNG BÁO"
    entities = [FakeEntity("custom_emoji", 0, 2, "111")]
    assert parse_emoji_units(text, entities) == [
        {"t": "emoji", "id": "111", "fb": "🔔"},
        {"t": "text", "v": "THÔNG BÁO"},
    ]


def test_parse_two_emoji_with_gap():
    text = "🔔X🔥"
    entities = [
        FakeEntity("custom_emoji", 0, 2, "111"),
        FakeEntity("custom_emoji", 3, 2, "222"),
    ]
    assert parse_emoji_units(text, entities) == [
        {"t": "emoji", "id": "111", "fb": "🔔"},
        {"t": "text", "v": "X"},
        {"t": "emoji", "id": "222", "fb": "🔥"},
    ]


def test_parse_ignores_non_custom_entities():
    text = "hello"
    entities = [FakeEntity("bold", 0, 5)]
    assert parse_emoji_units(text, entities) == [{"t": "text", "v": "hello"}]


def test_parse_plain_text_no_entities():
    assert parse_emoji_units("just text", []) == [{"t": "text", "v": "just text"}]


def test_parse_empty():
    assert parse_emoji_units("", []) == []


class FakeService:
    def __init__(self, mapping):
        self.mapping = mapping

    def get_rendered_html(self, pid):
        return self.mapping.get(pid, "")


def test_render_no_token_passthrough():
    svc = FakeService({})
    assert render("plain text", svc) == ("plain text", None)


def test_render_substitutes_token_and_escapes_surrounding():
    svc = FakeService({5: '<tg-emoji emoji-id="9">🔔</tg-emoji>'})
    text = "a < b {emo:5} end"
    out, mode = render(text, svc)
    assert mode == "HTML"
    assert out == 'a &lt; b <tg-emoji emoji-id="9">🔔</tg-emoji> end'


def test_render_missing_placeholder_drops_token():
    svc = FakeService({})
    out, mode = render("hi {emo:7} there", svc)
    assert mode == "HTML"
    assert out == "hi  there"


def test_render_multiple_tokens():
    svc = FakeService({1: "A", 2: "B"})
    out, mode = render("{emo:1}-{emo:2}", svc)
    assert out == "A-B"
    assert mode == "HTML"
