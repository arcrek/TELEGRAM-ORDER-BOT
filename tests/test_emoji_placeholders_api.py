"""Unit tests for emoji placeholder API schema."""
from src.dashboard.routers import emoji_placeholders


def test_response_token_format():
    resp = emoji_placeholders.EmojiPlaceholderResponse(
        id=5, name="Header", configured=False, raw_text=None
    )
    assert resp.token == "{emo:5}"
    assert resp.configured is False
