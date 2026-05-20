"""
Order notification service for sending new-order alerts to whitelisted chat IDs.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from telegram import Bot
from telegram.error import TelegramError
from src.database.models import Order
from src.database.services.notification_settings_service import (
    NotificationSettingsService,
)

logger = logging.getLogger(__name__)


class OrderNotificationService:
    """High-level service for sending order lifecycle notifications to admins."""

    def __init__(self, session: Session, bot: Optional[Bot] = None):
        """
        Initialize order notification service.

        Args:
            session: Database session
            bot: Telegram bot instance used to send notifications
        """
        self.session = session
        self.bot = bot
        self._settings_service = NotificationSettingsService(session)

    async def _send_async(self, event: str, order_id: str, delivery_data: Optional[str] = None) -> Dict[str, Any]:
        """
        Internal async implementation of sending an order notification.

        Args:
            event: Event name, e.g. 'created' or 'paid'
            order_id: Order ID
            delivery_data: Optional delivery data to include in the notification

        Returns:
            Result dict from NotificationService or a no-op result.
        """
        # If no bot instance is available, do nothing.
        if not self.bot:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "details": [],
                "skipped": "bot_not_available",
            }

        settings = self._settings_service.get_settings()
        whitelist_targets = self._settings_service.get_whitelist_targets(settings)

        if not settings.order_notify_enabled or not whitelist_targets:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "details": [],
                "skipped": "disabled_or_empty_whitelist",
            }

        if event == "created" and not settings.order_notify_on_created:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "details": [],
                "skipped": "event_disabled",
            }

        if event == "paid" and not settings.order_notify_on_paid:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "details": [],
                "skipped": "event_disabled",
            }

        order = self._get_order(order_id)
        if not order:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "details": [],
                "skipped": "order_not_found",
            }

        message = self._format_message(event, order, delivery_data=delivery_data)
        return await self.send_message_to_whitelist_async(message=message, targets=whitelist_targets)

    async def send_message_to_whitelist_async(
        self, message: str, targets: Optional[List[Dict[str, Optional[int]]]] = None
    ) -> Dict[str, Any]:
        """
        Send a raw message to order notification whitelist targets.
        """
        if not self.bot:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "details": [],
                "skipped": "bot_not_available",
            }

        if targets is None:
            settings = self._settings_service.get_settings()
            targets = self._settings_service.get_whitelist_targets(settings)

        results = {
            "total": len(targets),
            "success": 0,
            "failed": 0,
            "details": [],
        }

        for target in targets:
            chat_id = int(target["chat_id"])
            message_thread_id = target.get("message_thread_id")
            send_kwargs = {
                "chat_id": chat_id,
                "text": message,
            }
            if message_thread_id is not None:
                send_kwargs["message_thread_id"] = int(message_thread_id)

            try:
                send_message = self.bot.send_message
                if asyncio.iscoroutinefunction(send_message):
                    await send_message(**send_kwargs)
                else:
                    send_message(**send_kwargs)

                details = {
                    "success": True,
                    "telegram_user_id": chat_id,
                }
                if message_thread_id is not None:
                    details["message_thread_id"] = int(message_thread_id)
                results["details"].append(details)
                results["success"] += 1
            except TelegramError as e:
                error_msg = str(e)
                logger.error(
                    f"Failed to send order notification to chat {chat_id}: {error_msg}"
                )
                details = {
                    "success": False,
                    "error": error_msg,
                    "telegram_user_id": chat_id,
                }
                if message_thread_id is not None:
                    details["message_thread_id"] = int(message_thread_id)
                results["details"].append(details)
                results["failed"] += 1
            except Exception as e:
                error_msg = str(e)
                logger.error(
                    f"Unexpected error sending order notification to chat {chat_id}: {error_msg}",
                    exc_info=True,
                )
                details = {
                    "success": False,
                    "error": error_msg,
                    "telegram_user_id": chat_id,
                }
                if message_thread_id is not None:
                    details["message_thread_id"] = int(message_thread_id)
                results["details"].append(details)
                results["failed"] += 1

        return results

    def _get_order(self, order_id: str) -> Optional[Order]:
        """Fetch order by ID using the ORM session."""
        return self.session.query(Order).filter_by(id=order_id).first()

    def _format_message(self, event: str, order: Order, delivery_data: Optional[str] = None) -> str:
        """
        Format a notification message.

        Args:
            event: 'created' or 'paid'
            order: Order instance
            delivery_data: Optional string of delivery content to include
        """
        from src.database.models.bot_user import BotUser

        event_label = "NEW_ORDER_CREATED" if event == "created" else "ORDER_PAID"
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        items = getattr(order, "items", None) or []

        # Look up user info
        bot_user = self.session.query(BotUser).filter_by(telegram_user_id=order.user_id).first()
        username = (bot_user.username or "") if bot_user else ""
        name_parts = []
        if bot_user:
            if bot_user.first_name:
                name_parts.append(bot_user.first_name)
            if bot_user.last_name:
                name_parts.append(bot_user.last_name)
        name = " ".join(name_parts)

        short_order_id = order.id[:8] if len(order.id) >= 8 else order.id
        status_val = getattr(order.status, "value", str(order.status))

        lines = [
            f"🔔 {event_label}",
            f"• Order ID: {short_order_id}",
            "• Info",
            f"  ↳ ID: {order.user_id}",
            f"  ↳ Username: @{username}",
            f"  ↳ Name: {name}",
            f"• Status: {status_val}",
            f"• Total: {order.total_amount:,} VND",
        ]

        # Per-item details
        for item in items:
            product_name = (
                item.product.name if getattr(item, "product", None) else "N/A"
            )
            variation_name = (
                item.variation.name if getattr(item, "variation", None) else "N/A"
            )
            bonus_qty = item.bonus_quantity or 0
            qty_str = (
                f"{item.quantity} (+{bonus_qty} bonus)"
                if bonus_qty > 0
                else str(item.quantity)
            )
            lines.append(
                f"  ↳ {product_name} [{variation_name}] × {qty_str} — {item.subtotal:,} VND"
            )

        # Delivery data section
        lines.append("• Order details:")
        if delivery_data:
            for line in delivery_data.splitlines():
                lines.append(f"  ↳ {line}")
        else:
            lines.append("  ↳ (pending delivery)")

        lines.append(f"• At: {ts}")

        return "\n".join(lines)

    async def send_order_created_async(self, order_id: str) -> Dict[str, Any]:
        """
        Send notification for a newly created order (PENDING).

        Intended for use from async bot handlers.
        """
        return await self._send_async("created", order_id)

    async def send_order_paid_async(self, order_id: str, delivery_data: Optional[str] = None) -> Dict[str, Any]:
        """
        Send notification for a paid order (PAID).

        Intended for use from async contexts; sync callers should use
        the corresponding blocking wrapper.
        """
        return await self._send_async("paid", order_id, delivery_data=delivery_data)

    def prepare_order_paid_notification(
        self, order: Order, delivery_data: Optional[str] = None
    ) -> Optional[Tuple[str, List[Dict[str, Optional[int]]]]]:
        """Synchronously check settings and format an ORDER_PAID notification.

        Returns (message, targets) ready to pass to send_message_to_whitelist_async,
        or None when the notification is disabled / no targets are configured.
        All session access happens here (caller's thread); the returned tuple
        contains only plain strings/dicts so it is safe to use from any thread.
        """
        settings = self._settings_service.get_settings()
        targets = self._settings_service.get_whitelist_targets(settings)
        if not settings.order_notify_enabled:
            logger.debug(
                f"prepare_order_paid_notification: skipped {order.id} (order_notify_enabled=False)"
            )
            return None
        if not settings.order_notify_on_paid:
            logger.debug(
                f"prepare_order_paid_notification: skipped {order.id} (order_notify_on_paid=False)"
            )
            return None
        if not targets:
            logger.debug(
                f"prepare_order_paid_notification: skipped {order.id} (empty whitelist)"
            )
            return None
        return self._format_message("paid", order, delivery_data=delivery_data), targets

    def prepare_topup_notification(
        self, topup, bot_user
    ) -> Optional[Tuple[str, List[Dict[str, Optional[int]]]]]:
        """Synchronously check settings and format a BALANCE_TOPUP_PAID notification.

        Returns (message, targets) ready to pass to send_message_to_whitelist_async,
        or None when the notification is disabled / no targets are configured.
        All session access happens here (caller's thread).
        """
        settings = self._settings_service.get_settings()
        topup_id = getattr(topup, "id", "?")
        if not settings.order_notify_enabled:
            logger.debug(
                f"prepare_topup_notification: skipped {topup_id} (order_notify_enabled=False)"
            )
            return None
        if not settings.topup_notify_on_paid:
            logger.debug(
                f"prepare_topup_notification: skipped {topup_id} (topup_notify_on_paid=False)"
            )
            return None
        topup_targets = self._settings_service.get_topup_targets(settings)
        targets = topup_targets or self._settings_service.get_whitelist_targets(settings)
        if not targets:
            logger.debug(
                f"prepare_topup_notification: skipped {topup_id} (empty topup_notify_chat_ids and order_notify_whitelist_chat_ids)"
            )
            return None
        return self._format_topup_message(topup, bot_user), targets

    def send_order_paid(self, order_id: str, delivery_data: Optional[str] = None) -> Dict[str, Any]:
        """
        Blocking wrapper for send_order_paid_async, for use in sync flows
        such as the IPN server.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.send_order_paid_async(order_id, delivery_data=delivery_data),
                    )
                    return future.result()
            else:
                return loop.run_until_complete(self.send_order_paid_async(order_id, delivery_data=delivery_data))
        except RuntimeError:
            # No event loop
            return asyncio.run(self.send_order_paid_async(order_id, delivery_data=delivery_data))

    # ------------------------------------------------------------------
    # Topup notifications
    # ------------------------------------------------------------------

    def _format_topup_message(self, topup, bot_user) -> str:
        """
        Format a BALANCE_TOPUP_PAID admin notification.

        Mirrors the visual style of _format_message for orders.
        """
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        username = (bot_user.username or "") if bot_user else ""
        name_parts = []
        if bot_user:
            if bot_user.first_name:
                name_parts.append(bot_user.first_name)
            if bot_user.last_name:
                name_parts.append(bot_user.last_name)
        name = " ".join(name_parts)
        provider = getattr(topup, "payment_provider", None) or "unknown"

        lines = [
            "🔔 BALANCE_TOPUP_PAID",
            f"• Topup ID: {topup.id}",
            "• Info",
            f"  ↳ ID: {topup.user_id}",
            f"  ↳ Username: @{username}",
            f"  ↳ Name: {name}",
            f"• Amount: {topup.amount:,} VND",
            f"• Provider: {provider}",
            f"• At: {ts}",
        ]
        return "\n".join(lines)

    async def _send_topup_async(self, topup_id: str) -> Dict[str, Any]:
        """Async implementation of the BALANCE_TOPUP_PAID admin notification.

        Dispatch rules (mirroring the UPGRADE channel pattern):
        - Gated by the master ``order_notify_enabled`` and the
          ``topup_notify_on_paid`` toggle.
        - Routed to ``topup_notify_chat_ids`` when configured; otherwise falls
          back to ``order_notify_whitelist_chat_ids``.
        """
        if not self.bot:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "details": [],
                "skipped": "bot_not_available",
            }

        settings = self._settings_service.get_settings()

        if not settings.order_notify_enabled:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "details": [],
                "skipped": "disabled_or_empty_whitelist",
            }

        if not settings.topup_notify_on_paid:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "details": [],
                "skipped": "event_disabled",
            }

        topup_targets = self._settings_service.get_topup_targets(settings)
        if topup_targets:
            targets = topup_targets
        else:
            targets = self._settings_service.get_whitelist_targets(settings)

        if not targets:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "details": [],
                "skipped": "no_targets",
            }

        from src.database.services.topup_service import TopupService
        from src.database.models.bot_user import BotUser

        topup = TopupService(self.session).get_by_id(topup_id)
        if not topup:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "details": [],
                "skipped": "topup_not_found",
            }

        bot_user = self.session.query(BotUser).filter_by(id=topup.bot_user_id).first()
        message = self._format_topup_message(topup, bot_user)
        return await self.send_message_to_whitelist_async(message=message, targets=targets)

    def send_topup_paid(self, topup_id: str) -> Dict[str, Any]:
        """
        Blocking wrapper for _send_topup_async, for use in sync flows
        such as the IPN processor.

        Mirrors the shape of send_order_paid exactly.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self._send_topup_async(topup_id),
                    )
                    return future.result()
            else:
                return loop.run_until_complete(self._send_topup_async(topup_id))
        except RuntimeError:
            # No event loop
            return asyncio.run(self._send_topup_async(topup_id))

