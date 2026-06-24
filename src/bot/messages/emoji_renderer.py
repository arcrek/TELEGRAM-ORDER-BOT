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
# Case-insensitive: legitimate tokens are always lowercase (from /set_emo and the
# dashboard autocomplete), but display transforms like str.upper() on a product
# name turn "{emo:2}" into "{EMO:2}". Matching case-insensitively keeps those
# rendering instead of leaking the literal token.
_TOKEN_RE = re.compile(r"\{emo:(\d+)\}", re.IGNORECASE)


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
    if not _TOKEN_RE.search(text):
        return text, None

    escaped = html.escape(text)  # tokens contain no HTML-special chars, survive

    def _replace(match: "re.Match[str]") -> str:
        return service.get_rendered_html(int(match.group(1)))

    return _TOKEN_RE.sub(_replace, escaped), "HTML"


def split_icon(text: str, service) -> Tuple[str, Optional[str]]:
    """Resolve emoji tokens for a plain-text button label.

    Telegram inline-keyboard buttons render a custom emoji via the separate
    ``icon_custom_emoji_id`` field (Bot API 9.4), not inside the text. So we
    take the FIRST {emo:<id>} token's emoji as the button icon and strip that
    token from the visible text. Any remaining tokens (a button has just one
    icon) fall back to their plain unicode emoji.

    Returns (clean_text, icon_custom_emoji_id). icon is None when there is no
    usable emoji token.
    """
    if not _TOKEN_RE.search(text):
        return text, None

    icon_id: Optional[str] = None
    m = _TOKEN_RE.search(text)
    if m is not None:
        icon_id = service.get_first_emoji_id(int(m.group(1)))
        if icon_id:
            # Drop the token that became the icon; keep everything else.
            text = text[: m.start()] + text[m.end():]

    # Remaining tokens (or all of them, if the first had no usable emoji) become
    # their plain fallback text.
    text = _TOKEN_RE.sub(lambda mm: service.get_plain_text(int(mm.group(1))), text)
    return text.strip() or "​", icon_id


def substitute_plain(text: str, service) -> str:
    """Replace {emo:<id>} tokens with the placeholder's plain fallback unicode
    emoji. For plain-text contexts that cannot render <tg-emoji> custom emoji —
    e.g. a <pre> tap-to-copy block — where leaking the literal token is worse
    than showing the standard emoji char."""
    if not _TOKEN_RE.search(text):
        return text
    return _TOKEN_RE.sub(lambda m: service.get_plain_text(int(m.group(1))), text)


def substitute_tokens(html_text: str, service) -> str:
    """Replace {emo:<id>} tokens with placeholder <tg-emoji> HTML WITHOUT
    escaping the surrounding text. Use ONLY on strings that are ALREADY
    valid/escaped HTML (callers that build markup by hand and send parse_mode=HTML).
    The substituted placeholder HTML is itself safe (units_to_html escapes its parts)."""
    if not _TOKEN_RE.search(html_text):
        return html_text
    return _TOKEN_RE.sub(lambda m: service.get_rendered_html(int(m.group(1))), html_text)
