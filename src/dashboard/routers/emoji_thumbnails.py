"""Public image endpoint serving cached Telegram custom-emoji thumbnails.

Thumbnails are non-sensitive (public emoji art), so the endpoint is
unauthenticated — but it only serves/fetches custom_emoji_ids referenced by a
stored placeholder, so it can't be used to make the server fetch arbitrary ids.
"""
import logging
import os

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session
from telegram import Bot

from src.dashboard.auth import get_db
from src.database.services.emoji_placeholder_service import EmojiPlaceholderService
from src.database.services.emoji_thumbnail_service import EmojiThumbnailService

logger = logging.getLogger(__name__)
router = APIRouter()

_CACHE_HEADERS = {"Cache-Control": "public, max-age=86400"}


def _get_bot() -> Bot | None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set; cannot fetch emoji thumbnails")
        return None
    try:
        return Bot(token=token)
    except Exception as exc:
        logger.exception(f"Failed to build Bot for thumbnails: {exc}")
        return None


async def fetch_thumbnail_bytes(bot: Bot, custom_emoji_id: str) -> tuple[bytes, str] | None:
    """Download a custom emoji's static thumbnail. Returns (data, mime) or None."""
    stickers = await bot.get_custom_emoji_stickers([custom_emoji_id])
    if not stickers:
        return None
    thumb = stickers[0].thumbnail
    if thumb is None:
        return None
    tg_file = await bot.get_file(thumb.file_id)
    data = bytes(await tg_file.download_as_bytearray())
    return data, "image/webp"


@router.get("/{custom_emoji_id}")
async def get_emoji_thumbnail(custom_emoji_id: str, db: Session = Depends(get_db)):
    thumb_svc = EmojiThumbnailService(db)

    row = thumb_svc.get(custom_emoji_id)
    if row is not None and row.data is not None:
        return Response(content=row.data, media_type=row.mime or "image/webp", headers=_CACHE_HEADERS)

    # Abuse guard: never fetch ids not referenced by a stored placeholder.
    if custom_emoji_id not in EmojiPlaceholderService(db).referenced_emoji_ids():
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    # Fresh negative cache → don't re-hammer Telegram.
    if row is not None and not EmojiThumbnailService.is_stale_failure(row):
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    bot = _get_bot()
    if bot is None:
        thumb_svc.store_failure(custom_emoji_id)
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    try:
        result = await fetch_thumbnail_bytes(bot, custom_emoji_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Thumbnail fetch failed for {custom_emoji_id}: {exc}")
        result = None

    if result is None:
        thumb_svc.store_failure(custom_emoji_id)
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    data, mime = result
    thumb_svc.store(custom_emoji_id, data, mime)
    return Response(content=data, media_type=mime, headers=_CACHE_HEADERS)
