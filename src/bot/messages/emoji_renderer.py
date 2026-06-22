"""
Emoji rendering for the bot:
- parse_emoji_units: turn an incoming message (text + entities) into an ordered
  list of emoji/text units (capture side of /set_emo).
- render: replace {emo:<id>} tokens in outgoing text with <tg-emoji> HTML,
  HTML-escaping all surrounding human content first (render side).
"""
import html
import re
from typing import Iterable, List, Optional, Tuple

CUSTOM_EMOJI_TYPE = "custom_emoji"
_TOKEN_RE = re.compile(r"\{emo:(\d+)\}")


def parse_emoji_units(text: str, entities: Iterable) -> List[dict]:
    """
    Build an ordered unit list from message text + entities.

    Telegram entity offset/length are counted in UTF-16 code units, so we work
    in a UTF-16-LE byte buffer (2 bytes per code unit).
    """
    text = text or ""
    if not text:
        return []

    custom = [
        e
        for e in (entities or [])
        if getattr(e, "type", None) == CUSTOM_EMOJI_TYPE
    ]
    custom.sort(key=lambda e: e.offset)

    buf = text.encode("utf-16-le")
    total_units = len(buf) // 2

    def slice_u16(start: int, length: int) -> str:
        return buf[start * 2 : (start + length) * 2].decode("utf-16-le")

    units: List[dict] = []
    cursor = 0
    for e in custom:
        if e.offset > cursor:
            units.append({"t": "text", "v": slice_u16(cursor, e.offset - cursor)})
        units.append(
            {
                "t": "emoji",
                "id": str(e.custom_emoji_id),
                "fb": slice_u16(e.offset, e.length),
            }
        )
        cursor = e.offset + e.length

    if cursor < total_units:
        units.append({"t": "text", "v": slice_u16(cursor, total_units - cursor)})

    return units


def render(text: str, service) -> Tuple[str, Optional[str]]:
    """
    Expand {emo:<id>} tokens to <tg-emoji> HTML.

    Returns (text, None) if there is no token (sent as plain text, unchanged).
    Otherwise HTML-escapes the whole string first (so human content is safe),
    then replaces tokens with already-safe placeholder HTML, returning
    (html_string, "HTML").
    """
    if "{emo:" not in text:
        return text, None

    escaped = html.escape(text)  # tokens contain no HTML-special chars, survive

    def _replace(match: "re.Match[str]") -> str:
        return service.get_rendered_html(int(match.group(1)))

    return _TOKEN_RE.sub(_replace, escaped), "HTML"
