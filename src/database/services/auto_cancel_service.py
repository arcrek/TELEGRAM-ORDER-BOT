"""
Auto-cancel service for cancelling unpaid orders after 10 minutes.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import and_
from src.database.models import Order
from src.database.models.enums import OrderStatus
from src.database.services.order_service import OrderService
from src.database.services.topup_service import TopupService
from src.database.models.topup_order import TopupOrder
from src.bot.states.state_manager import StateManager
from src.payos.client import build_payos_client

logger = logging.getLogger(__name__)

PAYMENT_EXPIRE_MINUTES = 10

# Global state manager instance
state_manager = StateManager()


class AutoCancelService:
    """Service for automatically cancelling unpaid orders."""
    
    def __init__(self, session: Session, bot_instance=None, main_loop=None):
        """
        Initialize auto-cancel service.

        Args:
            session: Database session
            bot_instance: Optional Telegram bot instance for notifications
            main_loop: Optional asyncio loop the bot runs on; coroutines are
                scheduled onto it instead of a throwaway loop in this thread.
        """
        self.session = session
        self.bot = bot_instance
        self.main_loop = main_loop
        self.order_service = OrderService(session)

    def _run_coro(self, coro):
        """Run a bot coroutine from this (non-async) scheduler thread.

        Prefers scheduling onto the bot's main loop (where its httpx client
        lives); falls back to asyncio.run only when no running loop is set.
        """
        loop = self.main_loop
        if loop is not None and loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result(timeout=30)
        return asyncio.run(coro)
    
    def find_expired_pending_orders(self, minutes: int = 10) -> List[Order]:
        """
        Find PENDING orders older than specified minutes.
        
        Args:
            minutes: Number of minutes after which orders should be cancelled (default: 30)
        
        Returns:
            List of expired PENDING orders
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        
        orders = self.session.query(Order).filter(
            and_(
                Order.status == OrderStatus.PENDING,
                Order.created_at < cutoff_time
            )
        ).all()
        
        return orders
    
    def auto_cancel_order(self, order: Order, send_notification: bool = True) -> bool:
        """
        Automatically cancel an expired order.
        
        Args:
            order: Order to cancel
            send_notification: Whether to send notification to user
        
        Returns:
            True if cancelled successfully, False otherwise
        """
        try:
            # Double-check order is still PENDING (handle race conditions)
            self.session.refresh(order)
            if order.status != OrderStatus.PENDING:
                logger.info(
                    f"Order {order.id} is no longer PENDING (status: {order.status.value}), skipping auto-cancel"
                )
                return False

            # If this is a PayOS order, attempt to cancel the PayOS payment link too
            if getattr(order, "payment_provider", None) == "payos" and getattr(order, "payos_payment_link_id", None):
                try:
                    payos = build_payos_client()
                    payos.cancel_payment_link(
                        payment_link_id=str(order.payos_payment_link_id),
                        cancellation_reason="Auto-cancelled (timeout)",
                    )
                    logger.info(f"Cancelled PayOS payment link {order.payos_payment_link_id} for order {order.id}")
                except Exception as e:
                    logger.warning(f"Failed to cancel PayOS payment link for order {order.id}: {str(e)}")
            
            # Cancel the order
            cancelled_order = self.order_service.cancel_order(order.id)
            logger.info(f"Auto-cancelled order {order.id} (user: {cancelled_order.user_id})")
            
            # Delete the QR payment message if it exists
            if self.bot:
                user_state = state_manager.get_user_state(cancelled_order.user_id)
                if user_state and user_state.payment_message_id:
                    try:
                        self._run_coro(self.bot.delete_message(
                            chat_id=cancelled_order.user_id,
                            message_id=user_state.payment_message_id
                        ))
                        logger.info(f"Deleted payment message {user_state.payment_message_id} for auto-cancelled order {order.id}")
                        # Clear payment message ID from state
                        state_manager.update_user_state(cancelled_order.user_id, payment_message_id=None)
                    except Exception as e:
                        logger.warning(f"Could not delete payment message: {str(e)}")
            
            # Send notification if bot instance is available
            if send_notification and self.bot:
                try:
                    notification_message = (
                        f"⏰ Order Auto-Cancelled\n\n"
                        f"📦 Order ID: {cancelled_order.id}\n"
                        f"💰 Amount: {cancelled_order.total_amount:,} VND\n\n"
                        f"Your order was automatically cancelled because payment was not completed within 10 minutes.\n"
                        f"You can place a new order anytime."
                    )
                    self._run_coro(self.bot.send_message(
                        chat_id=cancelled_order.user_id,
                        text=notification_message
                    ))
                    logger.info(f"Sent auto-cancellation notification to user {cancelled_order.user_id}")
                except Exception as e:
                    logger.error(
                        f"Failed to send auto-cancellation notification to user {cancelled_order.user_id}: {str(e)}"
                    )
            
            return True
            
        except ValueError as e:
            # Order cannot be cancelled (race condition - already paid/cancelled)
            logger.warning(f"Cannot auto-cancel order {order.id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error auto-cancelling order {order.id}: {str(e)}", exc_info=True)
            return False
    
    def process_expired_orders(self, minutes: int = 10, send_notification: bool = True) -> dict:
        """
        Process all expired PENDING orders and cancel them.

        Args:
            minutes: Number of minutes after which orders should be cancelled
            send_notification: Whether to send notifications to users

        Returns:
            Dictionary with processing results
        """
        expired_orders = self.find_expired_pending_orders(minutes)

        results = {
            "found": len(expired_orders),
            "cancelled": 0,
            "failed": 0,
            "skipped": 0,
        }

        for order in expired_orders:
            if self.auto_cancel_order(order, send_notification):
                results["cancelled"] += 1
            else:
                results["skipped"] += 1

        if results["found"] > 0:
            logger.info(
                f"Auto-cancel processing: Found {results['found']} expired orders, "
                f"Cancelled {results['cancelled']}, Skipped {results['skipped']}"
            )

        return results

    # ------------------------------------------------------------------
    # Topup auto-cancel methods (parallel to the order variants above)
    # ------------------------------------------------------------------

    def find_expired_pending_topups(self, minutes: int = 10) -> List[TopupOrder]:
        """
        Find PENDING TopupOrders older than `minutes` minutes.

        Args:
            minutes: Age threshold in minutes (default: 30)

        Returns:
            List of expired PENDING TopupOrder instances
        """
        # Delegate to TopupService which already implements the cutoff query.
        return TopupService(self.session).find_expired_pending_topups(minutes)

    def auto_cancel_topup(self, topup: TopupOrder, send_notification: bool = True) -> bool:
        """
        Atomically cancel an expired PENDING TopupOrder.

        Args:
            topup: TopupOrder instance to cancel
            send_notification: Whether to send a Telegram notification to the user

        Returns:
            True if cancelled (or already cancelled gracefully), False on error
        """
        try:
            # Atomic cancellation via TopupService (WHERE status=PENDING).
            cancelled = TopupService(self.session).cancel_topup(topup.id)
            if not cancelled:
                logger.info(
                    f"Topup {topup.id} could not be cancelled atomically "
                    f"(already PAID or CANCELLED) — skipping"
                )
                return False

            logger.info(f"Auto-cancelled topup {topup.id} (user: {topup.user_id})")

            # If this was a PayOS topup, also cancel the payment link.
            if getattr(topup, "payment_provider", None) == "payos" and getattr(topup, "payos_payment_link_id", None):
                try:
                    payos = build_payos_client()
                    payos.cancel_payment_link(
                        payment_link_id=str(topup.payos_payment_link_id),
                        cancellation_reason="Auto-cancelled (timeout)",
                    )
                    logger.info(
                        f"Cancelled PayOS payment link {topup.payos_payment_link_id} "
                        f"for topup {topup.id}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to cancel PayOS payment link for topup {topup.id}: {str(e)}"
                    )

            # Send user notification if bot is available.
            if send_notification and self.bot:
                try:
                    notification_message = (
                        f"⏰ Nạp tiền đã hết hạn\n\n"
                        f"Mã nạp tiền: {topup.id}\n"
                        f"Số tiền: {topup.amount:,} VND\n\n"
                        f"Yêu cầu nạp tiền đã bị huỷ do không hoàn tất thanh toán trong 10 phút.\n"
                        f"Bạn có thể nạp tiền lại bất cứ lúc nào."
                    )
                    self._run_coro(self.bot.send_message(
                        chat_id=topup.user_id,
                        text=notification_message,
                    ))
                    logger.info(f"Sent auto-cancellation notification to user {topup.user_id} for topup {topup.id}")
                except Exception as e:
                    logger.error(
                        f"Failed to send auto-cancellation notification to user {topup.user_id} "
                        f"for topup {topup.id}: {str(e)}"
                    )

            return True

        except Exception as e:
            logger.error(f"Error auto-cancelling topup {topup.id}: {str(e)}", exc_info=True)
            return False

    def process_expired_topups(self, minutes: int = 10, send_notification: bool = True) -> dict:
        """
        Process all expired PENDING TopupOrders and cancel them.

        Args:
            minutes: Age threshold in minutes (default: 10)
            send_notification: Whether to send notifications to users

        Returns:
            Dictionary with keys: found, cancelled, failed, skipped
        """
        expired_topups = self.find_expired_pending_topups(minutes)

        results = {
            "found": len(expired_topups),
            "cancelled": 0,
            "failed": 0,
            "skipped": 0,
        }

        for topup in expired_topups:
            if self.auto_cancel_topup(topup, send_notification):
                results["cancelled"] += 1
            else:
                results["skipped"] += 1

        if results["found"] > 0:
            logger.info(
                f"Auto-cancel topup processing: Found {results['found']} expired topups, "
                f"Cancelled {results['cancelled']}, Skipped {results['skipped']}"
            )

        return results

    # ------------------------------------------------------------------
    # Expiry warning methods (1 minute before cancellation)
    # ------------------------------------------------------------------

    def find_expiring_soon_orders(self, expire_minutes: int = 10, warn_minutes: int = 1) -> List[Order]:
        """Find PENDING orders that have `warn_minutes` left before expiry."""
        now = datetime.now(timezone.utc)
        # Orders created between (expire_minutes) and (expire_minutes - warn_minutes) ago
        window_end = now - timedelta(minutes=expire_minutes - warn_minutes)
        window_start = now - timedelta(minutes=expire_minutes)
        return self.session.query(Order).filter(
            and_(
                Order.status == OrderStatus.PENDING,
                Order.created_at >= window_start,
                Order.created_at < window_end,
            )
        ).all()

    def find_expiring_soon_topups(self, expire_minutes: int = 10, warn_minutes: int = 1) -> List[TopupOrder]:
        """Find PENDING topups that have `warn_minutes` left before expiry."""
        now = datetime.now(timezone.utc)
        window_end = now - timedelta(minutes=expire_minutes - warn_minutes)
        window_start = now - timedelta(minutes=expire_minutes)
        return self.session.query(TopupOrder).filter(
            and_(
                TopupOrder.status == OrderStatus.PENDING,
                TopupOrder.created_at >= window_start,
                TopupOrder.created_at < window_end,
            )
        ).all()

    def send_expiry_warning_order(self, order: Order) -> bool:
        """Send a 1-minute-remaining warning to the user for a pending order."""
        if not self.bot:
            return False
        try:
            message = (
                f"⚠️ Thanh toán sắp hết hạn!\n\n"
                f"📦 Đơn hàng: {order.id}\n"
                f"💰 Số tiền: {order.total_amount:,} VND\n\n"
                f"Bạn còn 1 phút để hoàn tất thanh toán. "
                f"Đơn hàng sẽ tự động bị huỷ nếu không thanh toán."
            )
            self._run_coro(self.bot.send_message(chat_id=order.user_id, text=message))
            logger.info(f"Sent expiry warning for order {order.id} to user {order.user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send expiry warning for order {order.id}: {str(e)}")
            return False

    def send_expiry_warning_topup(self, topup: TopupOrder) -> bool:
        """Send a 1-minute-remaining warning to the user for a pending topup."""
        if not self.bot:
            return False
        try:
            message = (
                f"⚠️ Nạp tiền sắp hết hạn!\n\n"
                f"💳 Mã nạp tiền: {topup.id}\n"
                f"💰 Số tiền: {topup.amount:,} VND\n\n"
                f"Bạn còn 1 phút để hoàn tất thanh toán. "
                f"Yêu cầu nạp tiền sẽ tự động bị huỷ nếu không thanh toán."
            )
            self._run_coro(self.bot.send_message(chat_id=topup.user_id, text=message))
            logger.info(f"Sent expiry warning for topup {topup.id} to user {topup.user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send expiry warning for topup {topup.id}: {str(e)}")
            return False

    def process_expiring_soon(self, warned_order_ids: set, warned_topup_ids: set) -> dict:
        """
        Send 1-minute warnings for orders/topups about to expire.
        Uses in-memory sets to avoid duplicate warnings per process lifetime.

        Returns counts of newly warned orders and topups.
        """
        results = {"orders_warned": 0, "topups_warned": 0}

        for order in self.find_expiring_soon_orders():
            if order.id not in warned_order_ids:
                if self.send_expiry_warning_order(order):
                    warned_order_ids.add(order.id)
                    results["orders_warned"] += 1

        for topup in self.find_expiring_soon_topups():
            if topup.id not in warned_topup_ids:
                if self.send_expiry_warning_topup(topup):
                    warned_topup_ids.add(topup.id)
                    results["topups_warned"] += 1

        return results
