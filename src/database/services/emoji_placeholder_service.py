"""
EmojiPlaceholderService — CRUD for emoji placeholders plus rendering captured
unit lists to Telegram <tg-emoji> HTML.
"""
import html
import json
from typing import List, Optional

from sqlalchemy.orm import Session

from src.database.models.emoji_placeholder import EmojiPlaceholder


class EmojiPlaceholderService:
    """CRUD + rendering for emoji placeholders."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # ---- queries -----------------------------------------------------------
    def list_all(self) -> List[EmojiPlaceholder]:
        return (
            self.session.query(EmojiPlaceholder)
            .order_by(EmojiPlaceholder.id.asc())
            .all()
        )

    def get(self, placeholder_id: int) -> Optional[EmojiPlaceholder]:
        return self.session.get(EmojiPlaceholder, placeholder_id)

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
        units: List[dict],
        raw_text: str,
        set_by: Optional[int],
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
    def units_to_html(units: List[dict]) -> str:
        parts: List[str] = []
        for unit in units:
            if unit.get("t") == "emoji":
                fallback = html.escape(unit.get("fb", ""))
                parts.append(
                    f'<tg-emoji emoji-id="{unit["id"]}">{fallback}</tg-emoji>'
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
