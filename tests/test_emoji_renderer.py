from dataclasses import dataclass
from typing import Optional

from src.bot.messages.emoji_renderer import parse_emoji_units


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
