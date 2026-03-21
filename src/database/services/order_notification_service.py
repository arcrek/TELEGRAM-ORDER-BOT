"""
Order notification service for sending new-order alerts to whitelisted chat IDs.
"""
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from telegram import Bot
from src.database.models import Order
from src.database.services.notification_service import NotificationService
from src.database.services.notification_settings_service import (
    NotificationSettingsService,
)


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

    async def _send_async(self, event: str, order_id: str) -> Dict[str, Any]:
        """
        Internal async implementation of sending an order notification.

        Args:
            event: Event name, e.g. 'created' or 'paid'
            order_id: Order ID

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
        whitelist = self._settings_service.get_whitelist_chat_ids(settings)

        if not settings.order_notify_enabled or not whitelist:
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

        message = self._format_message(event, order)
        notification_service = NotificationService(self.session, bot=self.bot)

        # Use async variant to avoid nested event loop issues in async contexts.
        return await notification_service.send_notification_to_multiple_users_async(
            telegram_user_ids=whitelist,
            message=message,
        )

    def _get_order(self, order_id: str) -> Optional[Order]:
        """Fetch order by ID using the ORM session."""
        return self.session.query(Order).filter_by(id=order_id).first()

    def _format_message(self, event: str, order: Order) -> str:
        """
        Format a short, compact notification message.

        Args:
            event: 'created' or 'paid'
            order: Order instance
        """
        event_label = "NEW_ORDER_CREATED" if event == "created" else "ORDER_PAID"
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        items = getattr(order, "items", None) or []

        lines = [
            f"🔔 {event_label}",
            f"• Order ID: {order.id}",
            f"• User ID: {order.user_id}",
            f"• Status: {getattr(order.status, 'value', str(order.status))}",
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

        lines.append(f"• At: {ts}")

        return "\n".join(lines)

    async def send_order_created_async(self, order_id: str) -> Dict[str, Any]:
        """
        Send notification for a newly created order (PENDING).

        Intended for use from async bot handlers.
        """
        return await self._send_async("created", order_id)

    async def send_order_paid_async(self, order_id: str) -> Dict[str, Any]:
        """
        Send notification for a paid order (PAID).

        Intended for use from async contexts; sync callers should use
        the corresponding blocking wrapper.
        """
        return await self._send_async("paid", order_id)

    def send_order_paid(self, order_id: str) -> Dict[str, Any]:
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
                        self.send_order_paid_async(order_id),
                    )
                    return future.result()
            else:
                return loop.run_until_complete(self.send_order_paid_async(order_id))
        except RuntimeError:
            # No event loop
            return asyncio.run(self.send_order_paid_async(order_id))

