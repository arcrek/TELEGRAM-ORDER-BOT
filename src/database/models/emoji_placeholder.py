"""
EmojiPlaceholder model — reusable named snippets of Telegram custom (premium)
emoji captured from an admin message, referenced in text via {emo:<id>} tokens.
"""
from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from src.database.models.base import Base


class EmojiPlaceholder(Base):
    """A named placeholder whose content is an ordered list of emoji/text units."""

    __tablename__ = "emoji_placeholders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    # JSON-encoded ordered list of units, e.g.
    # [{"t": "emoji", "id": "5368...", "fb": "🔔"}, {"t": "text", "v": "THÔNG BÁO"}]
    # Null until configured via /set_emo.
    content = Column(Text, nullable=True)
    # Original message text the admin sent, for dashboard preview.
    raw_text = Column(Text, nullable=True)
    # Telegram user id of the admin who configured it.
    set_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
