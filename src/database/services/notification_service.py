"""
Notification service for sending custom notifications to bot users.
"""
import asyncio
import logging
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from telegram import Bot
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
        self, telegram_user_id: int, message: str
    ) -> Dict[str, any]:
        """
        Send notification to a single user (async).
        
        Args:
            telegram_user_id: Telegram user ID
            message: Notification message
        
        Returns:
            Dictionary with delivery status
        """
        if not self.bot:
            return {
                "success": False,
                "error": "Bot instance not available",
                "telegram_user_id": telegram_user_id,
            }
        
        try:
            # Support both async and sync bot.send_message for easier testing
            send_message = self.bot.send_message
            if asyncio.iscoroutinefunction(send_message):
                await send_message(chat_id=telegram_user_id, text=message)
            else:
                send_message(chat_id=telegram_user_id, text=message)
            logger.info(f"Notification sent successfully to user {telegram_user_id}")
            return {
                "success": True,
                "telegram_user_id": telegram_user_id,
            }
        except TelegramError as e:
            error_msg = str(e)
            logger.error(f"Failed to send notification to user {telegram_user_id}: {error_msg}")
            if isinstance(e, Forbidden):
                self.bot_user_service.update_user_active_status(telegram_user_id, False)
                logger.info(f"Marked user {telegram_user_id} as inactive (bot blocked)")
            return {
                "success": False,
                "error": error_msg,
                "telegram_user_id": telegram_user_id,
            }
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Unexpected error sending notification to user {telegram_user_id}: {error_msg}", exc_info=True)
            return {
                "success": False,
                "error": error_msg,
                "telegram_user_id": telegram_user_id,
            }

    def send_notification_to_user(
        self, telegram_user_id: int, message: str
    ) -> Dict[str, any]:
        """
        Send notification to a single user (synchronous wrapper).
        
        Args:
            telegram_user_id: Telegram user ID
            message: Notification message
        
        Returns:
            Dictionary with delivery status
        """
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, we need to use a different approach
                # Create a new task or use run_until_complete in a thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.send_notification_to_user_async(telegram_user_id, message)
                    )
                    return future.result()
            else:
                # Loop exists but not running, use it
                return loop.run_until_complete(
                    self.send_notification_to_user_async(telegram_user_id, message)
                )
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(
                self.send_notification_to_user_async(telegram_user_id, message)
            )

    async def send_notification_to_all_started_async(
        self, message: str
    ) -> Dict[str, any]:
        """
        Send notification to all users who pressed /start (async).
        
        Args:
            message: Notification message
        
        Returns:
            Dictionary with delivery statistics
        """
        users = self.bot_user_service.get_all_started_users()
        
        results = {
            "total": len(users),
            "success": 0,
            "failed": 0,
            "details": [],
        }
        
        for user in users:
            result = await self.send_notification_to_user_async(user.telegram_user_id, message)
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
        self, message: str
    ) -> Dict[str, any]:
        """
        Send notification to all users who pressed /start (synchronous wrapper).
        
        Args:
            message: Notification message
        
        Returns:
            Dictionary with delivery statistics
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.send_notification_to_all_started_async(message)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self.send_notification_to_all_started_async(message)
                )
        except RuntimeError:
            return asyncio.run(
                self.send_notification_to_all_started_async(message)
            )

    async def send_notification_to_active_users_async(
        self, message: str
    ) -> Dict[str, any]:
        """
        Send notification to active users only (async).
        
        Args:
            message: Notification message
        
        Returns:
            Dictionary with delivery statistics
        """
        users = self.bot_user_service.get_active_users()
        
        results = {
            "total": len(users),
            "success": 0,
            "failed": 0,
            "details": [],
        }
        
        for user in users:
            result = await self.send_notification_to_user_async(user.telegram_user_id, message)
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
        self, message: str
    ) -> Dict[str, any]:
        """
        Send notification to active users only (synchronous wrapper).
        
        Args:
            message: Notification message
        
        Returns:
            Dictionary with delivery statistics
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.send_notification_to_active_users_async(message)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self.send_notification_to_active_users_async(message)
                )
        except RuntimeError:
            return asyncio.run(
                self.send_notification_to_active_users_async(message)
            )

    async def send_notification_to_multiple_users_async(
        self, telegram_user_ids: List[int], message: str
    ) -> Dict[str, any]:
        """
        Send notification to multiple specific users (async).
        
        Args:
            telegram_user_ids: List of Telegram user IDs
            message: Notification message
        
        Returns:
            Dictionary with delivery statistics
        """
        results = {
            "total": len(telegram_user_ids),
            "success": 0,
            "failed": 0,
            "details": [],
        }
        
        for user_id in telegram_user_ids:
            result = await self.send_notification_to_user_async(user_id, message)
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
        self, telegram_user_ids: List[int], message: str
    ) -> Dict[str, any]:
        """
        Send notification to multiple specific users (synchronous wrapper).
        
        Args:
            telegram_user_ids: List of Telegram user IDs
            message: Notification message
        
        Returns:
            Dictionary with delivery statistics
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.send_notification_to_multiple_users_async(telegram_user_ids, message)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self.send_notification_to_multiple_users_async(telegram_user_ids, message)
                )
        except RuntimeError:
            return asyncio.run(
                self.send_notification_to_multiple_users_async(telegram_user_ids, message)
            )

