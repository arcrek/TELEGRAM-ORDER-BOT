"""
IPN order processor for handling payment confirmations and order fulfillment.
"""
import logging
from typing import Optional, Dict, Any
from src.database.connection import get_session_factory
from src.database.services.order_service import OrderService
from src.database.services.delivery_service import DeliveryService
from src.database.services.pre_uploaded_service import PreUploadedService
from src.database.services.supplier_order_service import SupplierOrderService
from src.database.models.enums import OrderStatus, DeliveryType
from telegram import Bot
from telegram.error import TelegramError
from src.bot.states.state_manager import StateManager

logger = logging.getLogger(__name__)

# Global state manager instance
state_manager = StateManager()


class IPNOrderProcessor:
    """Processes IPN notifications and fulfills orders."""

    def __init__(self, bot: Optional[Bot] = None, supplier_bot: Optional[Bot] = None):
        """
        Initialize IPN order processor.
        
        Args:
            bot: Optional Telegram bot instance for sending messages to customers
            supplier_bot: Optional Telegram bot instance for sending messages to suppliers
        """
        self.bot = bot
        self.supplier_bot = supplier_bot
        self.session_factory = get_session_factory()

    def process_payment_success(
        self, order_id: str, transaction_id: str, amount: int
    ) -> bool:
        """
        Process a successful payment.
        
        Args:
            order_id: Order ID
            transaction_id: Payment transaction ID
            amount: Payment amount
            
        Returns:
            True if processing successful, False otherwise
        """
        logger.info(f"=== Processing Payment Success ===")
        logger.info(f"Order ID: {order_id}, Transaction ID: {transaction_id}, Amount: {amount}")
        logger.info(f"Bot instance available: {self.bot is not None}")
        logger.info(f"Supplier bot instance available: {self.supplier_bot is not None}")
        
        session = self.session_factory()
        try:
            order_service = OrderService(session)
            delivery_service = DeliveryService(session)
            
            # Get order
            order = order_service.get_order_by_id(order_id)
            if not order:
                logger.error(f"Order {order_id} not found in database")
                return False
            
            logger.info(f"Found order: user_id={order.user_id}, status={order.status}, total={order.total_amount}")
            
            # Update order status to PAID
            order_service.update_order_status(
                order_id=order_id,
                status=OrderStatus.PAID,
                payment_transaction_id=transaction_id,
            )
            
            # Process the order (determine delivery type and trigger delivery)
            if not delivery_service.process_paid_order(order_id):
                logger.error(f"Failed to process order {order_id}")
                return False
            
            # Get delivery type and trigger appropriate delivery
            delivery_type = delivery_service.get_order_delivery_type(order_id)
            if not delivery_type:
                logger.error(f"Could not determine delivery type for order {order_id}")
                return False
            
            # Delete the QR payment message if it exists
            if self.bot:
                user_state = state_manager.get_user_state(order.user_id)
                if user_state and user_state.payment_message_id:
                    try:
                        self.bot.delete_message(
                            chat_id=order.user_id,
                            message_id=user_state.payment_message_id
                        )
                        logger.info(f"Deleted payment message {user_state.payment_message_id} for paid order {order_id}")
                        # Clear payment message ID from state
                        state_manager.update_user_state(order.user_id, payment_message_id=None)
                    except Exception as e:
                        logger.warning(f"Could not delete payment message: {str(e)}")
            
            logger.info(f"Delivery type: {delivery_type}")
            
            if delivery_type == DeliveryType.PRE_UPLOADED:
                # Handle pre-uploaded product delivery
                logger.info(f"Processing PRE_UPLOADED delivery for order {order_id}")
                self._handle_pre_uploaded_delivery(session, order_id, order.user_id)
            elif delivery_type == DeliveryType.SUPPLIER_BASED:
                # Handle supplier-based delivery
                logger.info(f"Processing SUPPLIER_BASED delivery for order {order_id}")
                self._handle_supplier_delivery(session, order_id, order.user_id)
            else:
                logger.warning(f"Unknown delivery type: {delivery_type}")
            
            logger.info(f"=== Payment Processing Complete for order {order_id} ===")
            return True
            
        except Exception as e:
            logger.error(f"Error processing payment success: {str(e)}", exc_info=True)
            session.rollback()
            return False
        finally:
            session.close()

    def process_payment_failure(
        self, order_id: str, result_code: int, message: str
    ) -> bool:
        """
        Process a failed payment.
        
        Args:
            order_id: Order ID
            result_code: Payment result code
            message: Error message
            
        Returns:
            True if processing successful, False otherwise
        """
        session = self.session_factory()
        try:
            order_service = OrderService(session)
            
            # Update order status to CANCELLED
            order_service.update_order_status(
                order_id=order_id,
                status=OrderStatus.CANCELLED,
            )
            
            # Send notification to user
            order = order_service.get_order_by_id(order_id)
            if order and self.bot:
                try:
                    error_message = (
                        f"❌ Payment failed for order {order_id}\n\n"
                        f"Reason: {message}\n"
                        f"Result Code: {result_code}\n\n"
                        f"Please try again or contact support."
                    )
                    self.bot.send_message(
                        chat_id=order.user_id,
                        text=error_message,
                    )
                except TelegramError as e:
                    logger.error(f"Failed to send failure notification: {str(e)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing payment failure: {str(e)}", exc_info=True)
            session.rollback()
            return False
        finally:
            session.close()

    def _handle_pre_uploaded_delivery(
        self, session, order_id: str, user_id: int
    ) -> None:
        """
        Handle pre-uploaded product delivery.
        
        Args:
            session: Database session
            order_id: Order ID
            user_id: Telegram user ID
        """
        try:
            pre_uploaded_service = PreUploadedService(session)
            order_service = OrderService(session)
            
            # Deliver products
            delivery_result = pre_uploaded_service.deliver_order(order_id)
            
            if not delivery_result:
                logger.error(f"Failed to deliver pre-uploaded products for order {order_id}")
                return
            
            if delivery_result["success"]:
                # Update order status to DELIVERED
                order_service.update_order_status(order_id, OrderStatus.DELIVERED)
                
                # Send products to user
                if self.bot:
                    self._send_pre_uploaded_products(
                        user_id, order_id, delivery_result["products"]
                    )
            else:
                # Some items failed
                logger.warning(
                    f"Partial delivery failure for order {order_id}: "
                    f"{delivery_result['failed_items']}"
                )
                # Update order status to PROCESSING (manual intervention needed)
                order_service.update_order_status(order_id, OrderStatus.PROCESSING)
                
                if self.bot:
                    error_message = (
                        f"⚠️ Order {order_id} partially delivered.\n\n"
                        f"Some items could not be delivered automatically.\n"
                        f"Please contact support."
                    )
                    try:
                        self.bot.send_message(chat_id=user_id, text=error_message)
                    except TelegramError as e:
                        logger.error(f"Failed to send partial delivery notification: {str(e)}")
                        
        except Exception as e:
            logger.error(f"Error handling pre-uploaded delivery: {str(e)}", exc_info=True)

    def _handle_supplier_delivery(
        self, session, order_id: str, user_id: int
    ) -> None:
        """
        Handle supplier-based delivery.
        
        Args:
            session: Database session
            order_id: Order ID
            user_id: Telegram user ID
        """
        try:
            supplier_order_service = SupplierOrderService(session)
            
            # Create supplier orders
            supplier_orders = supplier_order_service.create_supplier_orders_for_order(order_id)
            
            if not supplier_orders:
                logger.error(f"No supplier orders created for order {order_id}")
                return
            
            # Format and send notifications to suppliers
            notification_message = supplier_order_service.format_order_notification(order_id)
            
            # Use supplier bot if available, otherwise fall back to customer bot
            bot_to_use = self.supplier_bot or self.bot
            
            if notification_message and bot_to_use:
                for supplier_order in supplier_orders:
                    supplier = supplier_order.supplier
                    try:
                        # Send notification to supplier
                        sent_message = bot_to_use.send_message(
                            chat_id=supplier.telegram_user_id,
                            text=notification_message,
                        )
                        # Update supplier order with message ID
                        supplier_order_service.update_notification_message_id(
                            supplier_order.id, sent_message.message_id
                        )
                    except TelegramError as e:
                        logger.error(
                            f"Failed to send notification to supplier {supplier.id}: {str(e)}"
                        )
            
            # Send confirmation to user
            if self.bot:
                try:
                    user_message = (
                        f"✅ Payment confirmed for order {order_id}!\n\n"
                        f"Your order has been sent to our supplier.\n"
                        f"You will receive your product soon."
                    )
                    self.bot.send_message(chat_id=user_id, text=user_message)
                except TelegramError as e:
                    logger.error(f"Failed to send supplier delivery confirmation: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error handling supplier delivery: {str(e)}", exc_info=True)

    def _send_pre_uploaded_products(
        self, user_id: int, order_id: str, products: list[Dict[str, Any]]
    ) -> None:
        """
        Send pre-uploaded products to user via Telegram.
        
        Args:
            user_id: Telegram user ID
            order_id: Order ID
            products: List of product data dictionaries
        """
        try:
            # Send delivery confirmation
            confirmation_message = (
                f"✅ Payment confirmed!\n\n"
                f"📦 Order ID: {order_id}\n"
                f"📋 Products delivered:\n\n"
            )
            
            for idx, product in enumerate(products, 1):
                product_data = product.get("data", {})
                # Format product data (could be account credentials, codes, etc.)
                if isinstance(product_data, dict):
                    product_info = "\n".join(
                        f"  • {key}: {value}"
                        for key, value in product_data.items()
                    )
                else:
                    product_info = str(product_data)
                
                confirmation_message += f"{idx}. {product_info}\n\n"
            
            # Send message
            self.bot.send_message(chat_id=user_id, text=confirmation_message)
            
        except TelegramError as e:
            logger.error(f"Failed to send pre-uploaded products: {str(e)}")


# Global bot instances (set by bot applications)
_global_bot: Optional[Bot] = None
_global_supplier_bot: Optional[Bot] = None


def set_global_bot(bot: Bot) -> None:
    """
    Set the global customer bot instance for IPN processing.
    
    Args:
        bot: Telegram bot instance
    """
    global _global_bot
    _global_bot = bot


def set_global_supplier_bot(bot: Bot) -> None:
    """
    Set the global supplier bot instance for IPN processing.
    
    Args:
        bot: Telegram bot instance
    """
    global _global_supplier_bot
    _global_supplier_bot = bot


def get_global_customer_bot() -> Optional[Bot]:
    """
    Get the global customer bot instance.
    
    Returns:
        Customer bot instance or None
    """
    return _global_bot


def _create_bot_from_env() -> Optional[Bot]:
    """
    Create a Bot instance from environment variable if available.
    Used when running in IPN server container.
    
    Returns:
        Bot instance or None
    """
    import os
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if token:
        try:
            bot = Bot(token=token)
            logger.info("Created Telegram bot instance from TELEGRAM_BOT_TOKEN")
            return bot
        except Exception as e:
            logger.error(f"Failed to create bot from token: {e}")
    return None


def _create_supplier_bot_from_env() -> Optional[Bot]:
    """
    Create a supplier Bot instance from environment variable if available.
    
    Returns:
        Bot instance or None
    """
    import os
    token = os.getenv("SUPPLIER_TELEGRAM_BOT_TOKEN")
    if token:
        try:
            bot = Bot(token=token)
            logger.info("Created supplier Telegram bot instance from SUPPLIER_TELEGRAM_BOT_TOKEN")
            return bot
        except Exception as e:
            logger.error(f"Failed to create supplier bot from token: {e}")
    return None


def get_ipn_processor() -> IPNOrderProcessor:
    """
    Get IPN order processor instance with bots.
    If global bots are not set, tries to create them from environment variables.
    
    Returns:
        IPNOrderProcessor instance
    """
    global _global_bot, _global_supplier_bot
    
    # If bot not set, try to create from env (for IPN server container)
    if _global_bot is None:
        _global_bot = _create_bot_from_env()
    
    if _global_supplier_bot is None:
        _global_supplier_bot = _create_supplier_bot_from_env()
    
    return IPNOrderProcessor(bot=_global_bot, supplier_bot=_global_supplier_bot)

