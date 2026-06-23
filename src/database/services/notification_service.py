"""
Notification service for sending notifications to bot users.
"""
import asyncio
import logging
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from io import BytesIO
from telegram import Bot, InputFile
from telegram.error import Forbidden, TelegramError
from src.bot.messages.emoji_renderer import render as render_emoji
from src.database.services.bot_user_service import BotUserService
from src.database.services.emoji_placeholder_service import EmojiPlaceholderService

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications to bot users."""

    def __init__(self, session: Session, bot: Optional[Bot] = None):
        self.session = session
        self.bot = bot
        self.bot_user_service = BotUserService(session)
        self._is_async_send_message = bot is not None and asyncio.iscoroutinefunction(bot.send_message)
        self._is_async_send_photo = bot is not None and asyncio.iscoroutinefunction(bot.send_photo)

    def _render(self, message: str) -> Tuple[str, Optional[str]]:
        """Expand {emo:id} tokens to <tg-emoji> HTML. Returns (text, parse_mode).

        parse_mode is "HTML" when any token was expanded, else None (plain text).
        """
        return render_emoji(message, EmojiPlaceholderService(self.session))

    async def send_notification_to_user_async(
        self,
        telegram_user_id: int,
        message: str,
        image_bytes: Optional[bytes] = None,
        file_id_holder: Optional[dict] = None,
        parse_mode: Optional[str] = None,
    ) -> Dict[str, any]:
        """Send a notification (optionally with one image) to a single user.

        When parse_mode is None the message is rendered here (expanding {emo:id}
        tokens). Broadcast callers pre-render once and pass parse_mode through to
        avoid re-rendering per recipient.
        """
        if not self.bot:
            return {
                "success": False,
                "error": "Bot instance not available",
                "telegram_user_id": telegram_user_id,
            }

        if parse_mode is None:
            message, parse_mode = self._render(message)

        try:
            if image_bytes is None:
                send_kwargs: dict = {"chat_id": telegram_user_id, "text": message}
                if parse_mode is not None:
                    send_kwargs["parse_mode"] = parse_mode
                if self._is_async_send_message:
                    await self.bot.send_message(**send_kwargs)
                else:
                    self.bot.send_message(**send_kwargs)
            else:
                await self._send_photo_to_user(
                    telegram_user_id, message, image_bytes, file_id_holder, parse_mode
                )

            logger.info(f"Notification sent successfully to user {telegram_user_id}")
            return {"success": True, "telegram_user_id": telegram_user_id}
        except TelegramError as e:
            error_msg = str(e)
            logger.error(f"Failed to send notification to user {telegram_user_id}: {error_msg}")
            if isinstance(e, Forbidden):
                self.bot_user_service.update_user_active_status(telegram_user_id, False)
                logger.info(f"Marked user {telegram_user_id} as inactive (bot blocked)")
            return {"success": False, "error": error_msg, "telegram_user_id": telegram_user_id}
        except Exception as e:
            error_msg = str(e)
            logger.error(
                f"Unexpected error sending notification to user {telegram_user_id}: {error_msg}",
                exc_info=True,
            )
            return {"success": False, "error": error_msg, "telegram_user_id": telegram_user_id}

    async def _send_photo_to_user(
        self,
        telegram_user_id: int,
        message: str,
        image_bytes: bytes,
        file_id_holder: Optional[dict],
        parse_mode: Optional[str] = None,
    ) -> None:
        """Send a photo, reusing a captured file_id across a broadcast when available."""
        holder = file_id_holder if file_id_holder is not None else {"file_id": None}
        cached_id = holder.get("file_id")

        # Reuse the already-uploaded image (a file_id string) when we have one;
        # otherwise upload the raw bytes.
        photo = cached_id if cached_id else InputFile(BytesIO(image_bytes))

        use_caption = len(message) <= 1024
        caption = message if (use_caption and message) else None

        photo_kwargs: dict = {"chat_id": telegram_user_id, "photo": photo, "caption": caption}
        if parse_mode is not None and caption is not None:
            photo_kwargs["parse_mode"] = parse_mode

        if self._is_async_send_photo:
            sent = await self.bot.send_photo(**photo_kwargs)
        else:
            sent = self.bot.send_photo(**photo_kwargs)

        # Capture the file_id from the first successful upload for later recipients.
        if not cached_id and sent is not None:
            photos = getattr(sent, "photo", None)
            if photos:
                holder["file_id"] = photos[-1].file_id

        # Text longer than the caption limit goes in a separate message.
        if not use_caption and message:
            text_kwargs: dict = {"chat_id": telegram_user_id, "text": message}
            if parse_mode is not None:
                text_kwargs["parse_mode"] = parse_mode
            if self._is_async_send_message:
                await self.bot.send_message(**text_kwargs)
            else:
                self.bot.send_message(**text_kwargs)

    def _run_async(self, coro):
        """Run an async coroutine from synchronous context."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    return executor.submit(asyncio.run, coro).result()
            return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)

    async def _broadcast_to_users(
        self,
        user_ids: List[int],
        message: str,
        image_bytes: Optional[bytes],
        label: str,
    ) -> Dict[str, any]:
        """Send a notification to a list of user IDs, sharing a single image upload."""
        results = {"total": len(user_ids), "success": 0, "failed": 0, "details": []}
        file_id_holder: dict = {"file_id": None}
        # Render emoji tokens once for the whole broadcast (same message for all).
        rendered, parse_mode = self._render(message)
        for uid in user_ids:
            result = await self.send_notification_to_user_async(
                uid, rendered, image_bytes, file_id_holder, parse_mode
            )
            results["details"].append(result)
            if result["success"]:
                results["success"] += 1
            else:
                results["failed"] += 1
        logger.info(
            f"{label}: Total: {results['total']}, "
            f"Success: {results['success']}, Failed: {results['failed']}"
        )
        return results

    def send_notification_to_user(
        self, telegram_user_id: int, message: str, image_bytes: Optional[bytes] = None
    ) -> Dict[str, any]:
        """Send notification to a single user (synchronous wrapper)."""
        return self._run_async(
            self.send_notification_to_user_async(telegram_user_id, message, image_bytes)
        )

    async def send_notification_to_all_started_async(
        self, message: str, image_bytes: Optional[bytes] = None
    ) -> Dict[str, any]:
        """Send notification to all users who pressed /start (async)."""
        user_ids = [u.telegram_user_id for u in self.bot_user_service.get_all_started_users()]
        return await self._broadcast_to_users(user_ids, message, image_bytes, "Notification broadcast")

    def send_notification_to_all_started(
        self, message: str, image_bytes: Optional[bytes] = None
    ) -> Dict[str, any]:
        """Send notification to all users who pressed /start (synchronous wrapper)."""
        return self._run_async(self.send_notification_to_all_started_async(message, image_bytes))

    async def send_notification_to_active_users_async(
        self, message: str, image_bytes: Optional[bytes] = None
    ) -> Dict[str, any]:
        """Send notification to active users only (async)."""
        user_ids = [u.telegram_user_id for u in self.bot_user_service.get_active_users()]
        return await self._broadcast_to_users(user_ids, message, image_bytes, "Notification to active users")

    def send_notification_to_active_users(
        self, message: str, image_bytes: Optional[bytes] = None
    ) -> Dict[str, any]:
        """Send notification to active users only (synchronous wrapper)."""
        return self._run_async(self.send_notification_to_active_users_async(message, image_bytes))

    async def send_notification_to_multiple_users_async(
        self, telegram_user_ids: List[int], message: str, image_bytes: Optional[bytes] = None
    ) -> Dict[str, any]:
        """Send notification to multiple specific users (async)."""
        return await self._broadcast_to_users(
            telegram_user_ids, message, image_bytes, "Notification to multiple users"
        )

    def send_notification_to_multiple_users(
        self, telegram_user_ids: List[int], message: str, image_bytes: Optional[bytes] = None
    ) -> Dict[str, any]:
        """Send notification to multiple specific users (synchronous wrapper)."""
        return self._run_async(
            self.send_notification_to_multiple_users_async(telegram_user_ids, message, image_bytes)
        )
