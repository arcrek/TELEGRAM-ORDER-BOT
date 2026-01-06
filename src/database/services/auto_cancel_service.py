"""
Auto-cancel service for cancelling unpaid orders after 30 minutes.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import and_
from src.database.models import Order
from src.database.models.enums import OrderStatus
from src.database.services.order_service import OrderService
from src.bot.states.state_manager import StateManager

logger = logging.getLogger(__name__)

# Global state manager instance
state_manager = StateManager()


class AutoCancelService:
    """Service for automatically cancelling unpaid orders."""
    
    def __init__(self, session: Session, bot_instance=None):
        """
        Initialize auto-cancel service.
        
        Args:
            session: Database session
            bot_instance: Optional Telegram bot instance for sending notifications
        """
        self.session = session
        self.bot = bot_instance
        self.order_service = OrderService(session)
    
    def find_expired_pending_orders(self, minutes: int = 30) -> List[Order]:
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
            
            # Cancel the order
            cancelled_order = self.order_service.cancel_order(order.id)
            logger.info(f"Auto-cancelled order {order.id} (user: {cancelled_order.user_id})")
            
            # Delete the QR payment message if it exists
            if self.bot:
                user_state = state_manager.get_user_state(cancelled_order.user_id)
                if user_state and user_state.payment_message_id:
                    try:
                        self.bot.delete_message(
                            chat_id=cancelled_order.user_id,
                            message_id=user_state.payment_message_id
                        )
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
                        f"Your order was automatically cancelled because payment was not completed within 30 minutes.\n"
                        f"You can place a new order anytime."
                    )
                    self.bot.send_message(
                        chat_id=cancelled_order.user_id,
                        text=notification_message
                    )
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
    
    def process_expired_orders(self, minutes: int = 30, send_notification: bool = True) -> dict:
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

