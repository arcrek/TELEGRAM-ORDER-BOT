"""
EmojiThumbnail model — cached still thumbnail bytes for a Telegram custom
(premium) emoji, keyed by custom_emoji_id. `data` NULL = a fetch was attempted
but no image is available (negative cache; fetched_at marks the attempt time).
"""
from sqlalchemy import Column, DateTime, LargeBinary, String
from sqlalchemy.sql import func

from src.database.models.base import Base


class EmojiThumbnail(Base):
    """Global cache of custom-emoji thumbnail images."""

    __tablename__ = "emoji_thumbnails"

    custom_emoji_id = Column(String, primary_key=True)
    data = Column(LargeBinary, nullable=True)
    mime = Column(String, nullable=True)
    fetched_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
