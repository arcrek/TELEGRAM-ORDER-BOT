"""
EmojiPlaceholderService — CRUD for emoji placeholders plus rendering captured
unit lists to Telegram <tg-emoji> HTML.
"""
import html
import json

from sqlalchemy.orm import Session

from src.database.models.emoji_placeholder import EmojiPlaceholder


class EmojiPlaceholderService:
    """CRUD + rendering for emoji placeholders."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # ---- queries -----------------------------------------------------------
    def list_all(self) -> list[EmojiPlaceholder]:
        return (
            self.session.query(EmojiPlaceholder)
            .order_by(EmojiPlaceholder.id.asc())
            .all()
        )

    def get(self, placeholder_id: int) -> EmojiPlaceholder | None:
        return self.session.get(EmojiPlaceholder, placeholder_id)

    def referenced_emoji_ids(self) -> set:
        """All custom_emoji_ids referenced by any stored placeholder's content."""
        ids: set = set()
        for row in self.session.query(EmojiPlaceholder).all():
            if not row.content:
                continue
            for unit in json.loads(row.content):
                if unit.get("t") == "emoji" and unit.get("id"):
                    ids.add(str(unit["id"]))
        return ids

    # ---- mutations ---------------------------------------------------------
    def create(self, name: str) -> int:
        row = EmojiPlaceholder(name=name)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row.id

    def rename(self, placeholder_id: int, name: str) -> EmojiPlaceholder:
        row = self.get(placeholder_id)
        if row is None:
            raise ValueError(f"placeholder {placeholder_id} not found")
        row.name = name
        self.session.commit()
        self.session.refresh(row)
        return row

    def set_content(
        self,
        placeholder_id: int,
        units: list[dict],
        raw_text: str,
        set_by: int | None,
    ) -> EmojiPlaceholder:
        row = self.get(placeholder_id)
        if row is None:
            raise ValueError(f"placeholder {placeholder_id} not found")
        row.content = json.dumps(units, ensure_ascii=False)
        row.raw_text = raw_text
        row.set_by = set_by
        self.session.commit()
        self.session.refresh(row)
        return row

    def delete(self, placeholder_id: int) -> bool:
        row = self.get(placeholder_id)
        if row is None:
            return False
        self.session.delete(row)
        self.session.commit()
        return True

    # ---- rendering ---------------------------------------------------------
    @staticmethod
    def units_to_html(units: list[dict]) -> str:
        parts: list[str] = []
        for unit in units:
            if unit.get("t") == "emoji":
                fallback = html.escape(unit.get("fb", ""))
                parts.append(
                    f'<tg-emoji emoji-id="{html.escape(str(unit["id"]), quote=True)}">{fallback}</tg-emoji>'
                )
            else:
                parts.append(html.escape(unit.get("v", "")))
        return "".join(parts)

    def get_rendered_html(self, placeholder_id: int) -> str:
        """Return rendered HTML for a placeholder, or '' if missing/empty."""
        row = self.get(placeholder_id)
        if row is None or not row.content:
            return ""
        return self.units_to_html(json.loads(row.content))

    @staticmethod
    def units_to_plain(units: list[dict]) -> str:
        """Plain-text rendering: emoji units become their fallback char, text
        units their literal value. For contexts that cannot render <tg-emoji>."""
        parts: list[str] = []
        for unit in units:
            if unit.get("t") == "emoji":
                parts.append(unit.get("fb", ""))
            else:
                parts.append(unit.get("v", ""))
        return "".join(parts)

    def get_plain_text(self, placeholder_id: int) -> str:
        """Return the placeholder's plain fallback text, or '' if missing/empty."""
        row = self.get(placeholder_id)
        if row is None or not row.content:
            return ""
        return self.units_to_plain(json.loads(row.content))

    def get_first_emoji_id(self, placeholder_id: int) -> str | None:
        """Return the custom_emoji_id of the placeholder's first emoji unit, or
        None if the placeholder is missing/empty or holds no emoji. Used to set a
        button's icon_custom_emoji_id (one icon per button)."""
        row = self.get(placeholder_id)
        if row is None or not row.content:
            return None
        for unit in json.loads(row.content):
            if unit.get("t") == "emoji" and unit.get("id"):
                return str(unit["id"])
        return None
