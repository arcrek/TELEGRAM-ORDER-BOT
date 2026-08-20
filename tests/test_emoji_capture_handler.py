from dataclasses import dataclass, field

from src.bot.handlers.emoji_admin import extract_units_from_message


@dataclass
class FakeEntity:
    type: str
    offset: int
    length: int
    custom_emoji_id: str | None = None


@dataclass
class FakeMessage:
    text: str
    entities: list[FakeEntity] = field(default_factory=list)


def test_extract_units_from_message():
    msg = FakeMessage(text="🔔OK", entities=[FakeEntity("custom_emoji", 0, 2, "111")])
    assert extract_units_from_message(msg) == [
        {"t": "emoji", "id": "111", "fb": "🔔"},
        {"t": "text", "v": "OK"},
    ]
