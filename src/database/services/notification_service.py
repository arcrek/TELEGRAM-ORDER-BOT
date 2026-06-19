"""
Notification service for sending custom notifications to bot users.
"""
import asyncio
import logging
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from io import BytesIO
from telegram import Bot, InputFile
from telegram.error import Forbidden, TelegramError
from src.database.services.bot_user_service import BotUserService

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications to bot users."""

    def __init__(self, session: Session, bot: Optional[Bot] = None):
        """
        Initialize notification service.
        
        Args:
            session: Database session
            bot: Telegram bot instance for sending messages
        """
        self.session = session
        self.bot = bot
        self.bot_user_service = BotUserService(session)

    async def send_notification_to_user_async(
        self,
        telegram_user_id: int,
        message: str,
        image_bytes: Optional[bytes] = None,
        file_id_holder: Optional[dict] = None,
    ) -> Dict[str, any]:
        """Send a notification (optionally with one image) to a single user."""
        if not self.bot:
            return {
                "success": False,
                "error": "Bot instance not available",
                "telegram_user_id": telegram_user_id,
            }

        try:
            if image_bytes is None:
                # Text-only path — unchanged.
                send_message = self.bot.send_message
                if asyncio.iscoroutinefunction(send_message):
                    await send_message(chat_id=telegram_user_id, text=message)
                else:
                    send_message(chat_id=telegram_user_id, text=message)
            else:
                await self._send_photo_to_user(
                    telegram_user_id, message, image_bytes, file_id_holder
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
    ) -> None:
        """Send a photo, reusing a captured file_id across a broadcast when available."""
        holder = file_id_holder if file_id_holder is not None else {"file_id": None}
        cached_id = holder.get("file_id")

        # Reuse the already-uploaded image (a file_id string) when we have one;
        # otherwise upload the raw bytes.
        photo = cached_id if cached_id else InputFile(BytesIO(image_bytes))

        use_caption = len(message) <= 1024
        caption = message if (use_caption and message) else None

        send_photo = self.bot.send_photo
        if asyncio.iscoroutinefunction(send_photo):
            sent = await send_photo(chat_id=telegram_user_id, photo=photo, caption=caption)
        else:
            sent = send_photo(chat_id=telegram_user_id, photo=photo, caption=caption)

        # Capture the file_id from the first successful upload for later recipients.
        if not cached_id and sent is not None:
            photos = getattr(sent, "photo", None)
            if photos:
                holder["file_id"] = photos[-1].file_id

        # Text longer than the caption limit goes in a separate message.
        if not use_caption and message:
            send_message = self.bot.send_message
            if asyncio.iscoroutinefunction(send_message):
                await send_message(chat_id=telegram_user_id, text=message)
            else:
                send_message(chat_id=telegram_user_id, text=message)

    def send_notification_to_user(
        self, telegram_user_id: int, message: str, image_bytes: Optional[bytes] = None
    ) -> Dict[str, any]:
        """Send notification to a single user (synchronous wrapper)."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.send_notification_to_user_async(
                            telegram_user_id, message, image_bytes
                        ),
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self.send_notification_to_user_async(
                        telegram_user_id, message, image_bytes
                    )
                )
        except RuntimeError:
            return asyncio.run(
                self.send_notification_to_user_async(
                    telegram_user_id, message, image_bytes
                )
            )

    async def send_notification_to_all_started_async(
        self, message: str, image_bytes: Optional[bytes] = None
    ) -> Dict[str, any]:
        """
        Send notification to all users who pressed /start (async).

        Args:
            message: Notification message
            image_bytes: Optional image to attach

        Returns:
            Dictionary with delivery statistics
        """
        users = self.bot_user_service.get_all_started_users()
        results = {"total": len(users), "success": 0, "failed": 0, "details": []}
        file_id_holder = {"file_id": None}

        for user in users:
            result = await self.send_notification_to_user_async(
                user.telegram_user_id, message, image_bytes, file_id_holder
            )
            results["details"].append(result)

            if result["success"]:
                results["success"] += 1
            else:
                results["failed"] += 1

        logger.info(
            f"Notification broadcast: Total: {results['total']}, "
            f"Success: {results['success']}, Failed: {results['failed']}"
        )

        return results

    def send_notification_to_all_started(
        self, message: str, image_bytes: Optional[bytes] = None
    ) -> Dict[str, any]:
        """Send notification to all users who pressed /start (synchronous wrapper)."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.send_notification_to_all_started_async(message, image_bytes)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self.send_notification_to_all_started_async(message, image_bytes)
                )
        except RuntimeError:
            return asyncio.run(
                self.send_notification_to_all_started_async(message, image_bytes)
            )

    async def send_notification_to_active_users_async(
        self, message: str, image_bytes: Optional[bytes] = None
    ) -> Dict[str, any]:
        """
        Send notification to active users only (async).

        Args:
            message: Notification message
            image_bytes: Optional image to attach

        Returns:
            Dictionary with delivery statistics
        """
        users = self.bot_user_service.get_active_users()
        results = {"total": len(users), "success": 0, "failed": 0, "details": []}
        file_id_holder = {"file_id": None}

        for user in users:
            result = await self.send_notification_to_user_async(
                user.telegram_user_id, message, image_bytes, file_id_holder
            )
            results["details"].append(result)

            if result["success"]:
                results["success"] += 1
            else:
                results["failed"] += 1

        logger.info(
            f"Notification to active users: Total: {results['total']}, "
            f"Success: {results['success']}, Failed: {results['failed']}"
        )

        return results

    def send_notification_to_active_users(
        self, message: str, image_bytes: Optional[bytes] = None
    ) -> Dict[str, any]:
        """Send notification to active users only (synchronous wrapper)."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.send_notification_to_active_users_async(message, image_bytes)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self.send_notification_to_active_users_async(message, image_bytes)
                )
        except RuntimeError:
            return asyncio.run(
                self.send_notification_to_active_users_async(message, image_bytes)
            )

    async def send_notification_to_multiple_users_async(
        self, telegram_user_ids: List[int], message: str, image_bytes: Optional[bytes] = None
    ) -> Dict[str, any]:
        """
        Send notification to multiple specific users (async).

        Args:
            telegram_user_ids: List of Telegram user IDs
            message: Notification message
            image_bytes: Optional image to attach

        Returns:
            Dictionary with delivery statistics
        """
        results = {"total": len(telegram_user_ids), "success": 0, "failed": 0, "details": []}
        file_id_holder = {"file_id": None}

        for user_id in telegram_user_ids:
            result = await self.send_notification_to_user_async(
                user_id, message, image_bytes, file_id_holder
            )
            results["details"].append(result)

            if result["success"]:
                results["success"] += 1
            else:
                results["failed"] += 1

        logger.info(
            f"Notification to multiple users: Total: {results['total']}, "
            f"Success: {results['success']}, Failed: {results['failed']}"
        )

        return results

    def send_notification_to_multiple_users(
        self, telegram_user_ids: List[int], message: str, image_bytes: Optional[bytes] = None
    ) -> Dict[str, any]:
        """Send notification to multiple specific users (synchronous wrapper)."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.send_notification_to_multiple_users_async(
                            telegram_user_ids, message, image_bytes
                        )
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self.send_notification_to_multiple_users_async(
                        telegram_user_ids, message, image_bytes
                    )
                )
        except RuntimeError:
            return asyncio.run(
                self.send_notification_to_multiple_users_async(
                    telegram_user_ids, message, image_bytes
                )
            )

