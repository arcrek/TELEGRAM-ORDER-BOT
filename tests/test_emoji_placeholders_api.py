"""Unit tests for emoji placeholder API schema."""
from src.dashboard.routers import emoji_placeholders
from src.dashboard.routers.emoji_placeholders import EmojiUnit, _parse_units


def test_response_token_format():
    resp = emoji_placeholders.EmojiPlaceholderResponse(
        id=5, name="Header", configured=False, raw_text=None
    )
    assert resp.token == "{emo:5}"
    assert resp.configured is False

def test_parse_units_maps_emoji_and_text():
    import json
    content = json.dumps([
        {"t": "emoji", "id": "111", "fb": "🔔"},
        {"t": "text", "v": "THÔNG BÁO"},
    ])
    units = _parse_units(content)
    assert units == [
        EmojiUnit(type="emoji", emoji_id="111", fallback="🔔"),
        EmojiUnit(type="text", value="THÔNG BÁO"),
    ]


def test_parse_units_empty_for_unconfigured():
    assert _parse_units(None) == []
    assert _parse_units("") == []
