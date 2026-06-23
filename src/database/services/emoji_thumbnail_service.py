"""
EmojiThumbnailService — cache CRUD for custom-emoji thumbnails, plus a
negative-cache staleness check.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.database.models.emoji_thumbnail import EmojiThumbnail

THUMBNAIL_NEGATIVE_TTL = timedelta(hours=1)


class EmojiThumbnailService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, custom_emoji_id: str) -> Optional[EmojiThumbnail]:
        return self.session.get(EmojiThumbnail, custom_emoji_id)

    def store(self, custom_emoji_id: str, data: bytes, mime: str) -> EmojiThumbnail:
        row = self.get(custom_emoji_id)
        if row is None:
            row = EmojiThumbnail(custom_emoji_id=custom_emoji_id)
            self.session.add(row)
        row.data = data
        row.mime = mime
        row.fetched_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.session.commit()
        self.session.refresh(row)
        return row

    def store_failure(self, custom_emoji_id: str) -> EmojiThumbnail:
        row = self.get(custom_emoji_id)
        if row is None:
            row = EmojiThumbnail(custom_emoji_id=custom_emoji_id)
            self.session.add(row)
        row.data = None
        row.mime = None
        row.fetched_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.session.commit()
        self.session.refresh(row)
        return row

    @staticmethod
    def is_stale_failure(row: EmojiThumbnail) -> bool:
        """True if this is a failure row (no data) older than the negative TTL."""
        if row.data is not None:
            return False
        fetched = row.fetched_at
        if fetched is None:
            return True
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - fetched > THUMBNAIL_NEGATIVE_TTL
