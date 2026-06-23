from dataclasses import dataclass
from typing import Optional

from src.bot.messages.emoji_renderer import (
    parse_emoji_units,
    render,
    split_icon,
    substitute_tokens,
)


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


# --- substitute_tokens tests ---


def test_substitute_tokens_no_token_passthrough():
    """No {emo:} token: string returned unchanged, existing HTML is NOT escaped."""
    svc = FakeService({})
    html_text = "<b>hello &amp; world</b>"
    result = substitute_tokens(html_text, svc)
    assert result == "<b>hello &amp; world</b>"


def test_substitute_tokens_replaces_token_leaves_html_intact():
    """Token replaced by service HTML; surrounding already-escaped HTML untouched."""
    tg = '<tg-emoji emoji-id="9">🔔</tg-emoji>'
    svc = FakeService({5: tg})
    html_text = "<b>Sản phẩm &amp; {emo:5} giá tốt</b>"
    result = substitute_tokens(html_text, svc)
    assert result == f"<b>Sản phẩm &amp; {tg} giá tốt</b>"


def test_substitute_tokens_missing_placeholder_drops_token():
    """Missing placeholder: token is replaced with empty string (dropped)."""
    svc = FakeService({})
    html_text = "<b>Tên {emo:99}</b>"
    result = substitute_tokens(html_text, svc)
    assert result == "<b>Tên </b>"


# --- split_icon tests (button labels: emoji goes to icon_custom_emoji_id) ---


class FakeIconService:
    """first_emoji maps placeholder_id -> custom_emoji_id; plain maps -> fallback text."""

    def __init__(self, first_emoji=None, plain=None):
        self.first_emoji = first_emoji or {}
        self.plain = plain or {}

    def get_first_emoji_id(self, pid):
        return self.first_emoji.get(pid)

    def get_plain_text(self, pid):
        return self.plain.get(pid, "")


def test_split_icon_no_token_passthrough():
    assert split_icon("ChatGPT", FakeIconService()) == ("ChatGPT", None)


def test_split_icon_leading_token_becomes_icon_and_is_stripped():
    svc = FakeIconService(first_emoji={5: "9988"})
    text, icon = split_icon("{emo:5} ChatGPT", svc)
    assert icon == "9988"
    assert text == "ChatGPT"


def test_split_icon_token_mid_text():
    svc = FakeIconService(first_emoji={5: "9988"})
    text, icon = split_icon("Pro {emo:5} plan", svc)
    assert icon == "9988"
    assert text == "Pro  plan".strip()  # leading/trailing trimmed, inner spacing kept


def test_split_icon_missing_emoji_falls_back_to_plain():
    """Token whose placeholder has no usable emoji: no icon, plain fallback text."""
    svc = FakeIconService(first_emoji={}, plain={7: "⭐"})
    text, icon = split_icon("{emo:7} VIP", svc)
    assert icon is None
    assert text == "⭐ VIP"


def test_split_icon_first_is_icon_rest_are_plain():
    svc = FakeIconService(first_emoji={1: "111"}, plain={2: "🔥"})
    text, icon = split_icon("{emo:1} hot {emo:2}", svc)
    assert icon == "111"
    assert text == "hot 🔥"


def test_split_icon_icon_only_keeps_non_empty_button_text():
    svc = FakeIconService(first_emoji={1: "111"}, plain={1: "⭐"})
    text, icon = split_icon("{emo:1}", svc)
    assert icon == "111"
    assert text == "​"
