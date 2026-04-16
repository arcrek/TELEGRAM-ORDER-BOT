"""
Order processor for IPN (Instant Payment Notification) from any payment provider.

Used by both PayOS (dashboard webhook) and Pay2S (IPN server). Receives payment
confirmations, updates order status, and fulfills delivery (pre-uploaded or supplier-based).
"""
import asyncio
import logging
import os
import threading
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional, Dict, Any
from src.database.connection import get_session_factory
from src.database.services.order_service import OrderService
from src.database.services.delivery_service import DeliveryService
from src.database.services.pre_uploaded_service import PreUploadedService
from src.database.services.supplier_order_service import SupplierOrderService
from src.database.services.order_notification_service import OrderNotificationService
from src.database.models.enums import OrderStatus, DeliveryType
from telegram import Bot
from telegram.error import TelegramError
from src.bot.states.state_manager import StateManager

logger = logging.getLogger(__name__)

# Directory for storing delivery files
DELIVERY_FILES_DIR = Path(__file__).resolve().parent.parent.parent / "delivery_data"
DELIVERY_FILES_DIR.mkdir(exist_ok=True)


# Thread-local storage for the "request" event loop when processing payment in a
# worker thread (e.g. FastAPI webhook runs processor in executor). run_async then
# schedules Telegram coroutines on this loop instead of creating a new one
# (which can cause "Event loop is closed" with telegram/httpx/anyio).
_request_loop_local: threading.local = threading.local()


def _get_request_loop():
    """Get the request loop set by process_payment_success when run from FastAPI."""
    return getattr(_request_loop_local, "loop", None)


def _set_request_loop(loop):
    _request_loop_local.loop = loop


def _clear_request_loop():
    if hasattr(_request_loop_local, "loop"):
        del _request_loop_local.loop


def run_async(coro):
    """
    Run an async coroutine from a synchronous context.

    - When a request loop was set (e.g. PayOS webhook runs processor in executor):
      schedules the coroutine on that loop via run_coroutine_threadsafe and waits.
    - Otherwise (e.g. Pay2S Flask IPN): runs the coroutine on the current or a
      new event loop in this thread.
    """
    request_loop = _get_request_loop()
    if request_loop is not None and request_loop.is_running():
        # We're in a worker thread; schedule on the main loop to avoid
        # creating/closing a second loop (telegram/httpx/anyio break otherwise)
        future = asyncio.run_coroutine_threadsafe(coro, request_loop)
        return future.result(timeout=30)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Caller is on the loop thread; must not block. Use a new loop in a thread.
            import concurrent.futures
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                return executor.submit(run_in_thread).result(timeout=30)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)
    except Exception as e:
        logger.error(f"Error in run_async: {str(e)}", exc_info=True)
        raise


# Global state manager instance
state_manager = StateManager()


class IPNOrderProcessor:
    """
    Processes payment success/failure and fulfills orders.

    Used by PayOS webhook and Pay2S IPN; payment-agnostic (order_id, transaction_id, amount).
    """

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
        self,
        order_id: str,
        transaction_id: str,
        amount: int,
        *,
        request_loop=None,
    ) -> bool:
        """
        Process a successful payment.

        Args:
            order_id: Order ID
            transaction_id: Payment transaction ID
            amount: Payment amount
            request_loop: When called from an async context (e.g. FastAPI webhook),
                pass the running event loop so Telegram calls are scheduled on it
                instead of creating a second loop (avoids "Event loop is closed").

        Returns:
            True if processing successful, False otherwise
        """
        if request_loop is not None:
            _set_request_loop(request_loop)
        try:
            return self._process_payment_success_impl(order_id, transaction_id, amount)
        finally:
            if request_loop is not None:
                _clear_request_loop()

    def _process_payment_success_impl(
        self, order_id: str, transaction_id: str, amount: int
    ) -> bool:
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

            # Check if order is already delivered to prevent duplicate deliveries
            if order.status == OrderStatus.DELIVERED:
                logger.warning(f"Order {order_id} is already DELIVERED. Skipping duplicate delivery.")
                return True  # Return True because order was already processed successfully

            # Validate amount: IPN amount must match order total
            if amount != order.total_amount:
                logger.error(f"Amount mismatch! IPN amount: {amount}, Order total: {order.total_amount}. Skipping delivery.")
                return False

            logger.info(f"Amount validated: IPN amount ({amount}) matches order total ({order.total_amount})")

            # Check if order is already paid (duplicate IPN)
            if order.status == OrderStatus.PAID:
                logger.warning(f"Order {order_id} is already PAID but not delivered. Will attempt delivery.")

            # Update order status to PAID
            order_service.update_order_status(
                order_id=order_id,
                status=OrderStatus.PAID,
                payment_transaction_id=transaction_id,
            )

            # ORDER_PAID notification is sent after delivery (in _handle_pre_uploaded_delivery)
            # so that it can include the actual delivery data.

            # Process the order (determine delivery type and trigger delivery)
            if not delivery_service.process_paid_order(order_id):
                logger.error(f"Failed to process order {order_id}")
                return False

            # Get delivery type and trigger appropriate delivery
            delivery_type = delivery_service.get_order_delivery_type(order_id)
            if not delivery_type:
                logger.error(f"Could not determine delivery type for order {order_id}")
                return False

            # Delete all payment-related messages from database
            if self.bot:
                import json
                messages_deleted = 0

                # Read message IDs from database
                if order.payment_message_ids:
                    try:
                        message_ids = json.loads(order.payment_message_ids)
                        logger.info(f"Found {len(message_ids)} payment message IDs in database: {message_ids}")

                        for msg_id in message_ids:
                            try:
                                run_async(self.bot.delete_message(
                                    chat_id=order.user_id,
                                    message_id=msg_id
                                ))
                                messages_deleted += 1
                                logger.info(f"✓ Deleted message {msg_id}")
                            except Exception as e:
                                logger.warning(f"Could not delete message {msg_id}: {str(e)}")

                        # Clear payment message IDs from database
                        order.payment_message_ids = None
                        session.commit()
                        logger.info(f"✓ Successfully deleted {messages_deleted}/{len(message_ids)} payment messages for order {order_id}")
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse payment_message_ids: {str(e)}")
                else:
                    logger.info(f"No payment message IDs in database for order {order_id}")
            else:
                logger.warning(f"Bot instance not available to delete payment messages for order {order_id}")

            logger.info(f"Delivery type: {delivery_type}")

            delivery_success = False
            try:
                if delivery_type == DeliveryType.PRE_UPLOADED:
                    # Handle pre-uploaded product delivery
                    logger.info(f"Processing PRE_UPLOADED delivery for order {order_id}")
                    self._handle_pre_uploaded_delivery(session, order_id, order.user_id)
                    delivery_success = True
                elif delivery_type == DeliveryType.SUPPLIER_BASED:
                    # Supplier-based delivery is DISABLED
                    logger.warning(f"SUPPLIER_BASED delivery is disabled for order {order_id}")
                    # Send notification to user about disabled supplier delivery
                    if self.bot:
                        try:
                            user_message = (
                                f"⚠️ Order {order_id} payment confirmed!\n\n"
                                f"However, supplier-based delivery is currently disabled.\n"
                                f"Please contact support for assistance."
                            )
                            run_async(self.bot.send_message(chat_id=order.user_id, text=user_message))
                        except Exception as e:
                            logger.error(f"Failed to send supplier disabled notification: {str(e)}")
                    delivery_success = False
                else:
                    logger.error(f"Unknown delivery type: {delivery_type} for order {order_id}")
                    return False
            except Exception as e:
                logger.error(f"Error during delivery processing for order {order_id}: {str(e)}", exc_info=True)
                return False

            if delivery_success:
                logger.info(f"✓ Delivery completed successfully for order {order_id}")
            else:
                logger.error(f"✗ Delivery failed for order {order_id}")

            logger.info(f"=== Payment Processing Complete for order {order_id} ===")
            return delivery_success

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
                    run_async(self.bot.send_message(
                        chat_id=order.user_id,
                        text=error_message,
                    ))
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

        Raises:
            Exception: If delivery fails critically
        """
        pre_uploaded_service = PreUploadedService(session)
        order_service = OrderService(session)

        # Deliver products
        logger.info(f"Calling deliver_order for order {order_id}")
        delivery_result = pre_uploaded_service.deliver_order(order_id)

        if not delivery_result:
            logger.error(f"deliver_order returned None/False for order {order_id}")
            raise RuntimeError(f"deliver_order failed for order {order_id}")

        if delivery_result["success"]:
            # Send products to user BEFORE marking as DELIVERED
            if not self.bot:
                logger.error(
                    f"Bot instance is None! Cannot send products to user {user_id} for order {order_id}"
                )
                raise RuntimeError("Bot instance is None, cannot deliver products")

            logger.info(f"Bot available, sending products to user {user_id} for order {order_id}")
            delivery_sent = False
            delivery_content = None
            try:
                delivery_content = self._send_pre_uploaded_products(user_id, order_id, delivery_result["products"])
                delivery_sent = True
            finally:
                # Always mark DELIVERED once send completed, so status is correct even if
                # something raises after send (e.g. cleanup). Prevents "delivered but still processing".
                if delivery_sent:
                    order_service.update_order_status(order_id, OrderStatus.DELIVERED)
                    logger.info(f"✓ Order {order_id} marked as DELIVERED after successful product send")

            # Fire ORDER_PAID notification after delivery so it includes delivery data
            try:
                notify_service = OrderNotificationService(session, bot=self.bot)
                notify_service.send_order_paid(order_id, delivery_data=delivery_content)
            except Exception as e:
                logger.warning(f"Order paid notification failed for {order_id}: {e}")
            return

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
                run_async(self.bot.send_message(chat_id=user_id, text=error_message))
            except TelegramError as e:
                logger.error(f"Failed to send partial delivery notification: {str(e)}")

        # Treat partial delivery as failure so upstream returns processed=False
        raise RuntimeError(f"Partial delivery failure for order {order_id}")

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
                raise RuntimeError(f"No supplier orders created for order {order_id}")

            # Format and send notifications to suppliers
            notification_message = supplier_order_service.format_order_notification(order_id)

            # Use supplier bot if available, otherwise fall back to customer bot
            bot_to_use = self.supplier_bot or self.bot

            if notification_message and bot_to_use:
                for supplier_order in supplier_orders:
                    supplier = supplier_order.supplier
                    try:
                        # Send notification to supplier
                        sent_message = run_async(bot_to_use.send_message(
                            chat_id=supplier.telegram_user_id,
                            text=notification_message,
                        ))
                        # Update supplier order with message ID
                        supplier_order_service.update_notification_message_id(
                            supplier_order.id, sent_message.message_id
                        )
                    except TelegramError as e:
                        logger.error(
                            f"Failed to send notification to supplier {supplier.id}: {str(e)}"
                        )
                        raise
                    except Exception as e:
                        logger.error(
                            f"Error sending notification to supplier {supplier.id}: {str(e)}", exc_info=True
                        )
                        raise

            # Send confirmation to user
            if self.bot:
                try:
                    user_message = (
                        f"✅ Payment confirmed for order {order_id}!\n\n"
                        f"Your order has been sent to our supplier.\n"
                        f"You will receive your product soon."
                    )
                    run_async(self.bot.send_message(chat_id=user_id, text=user_message))
                except TelegramError as e:
                    logger.error(f"Failed to send supplier delivery confirmation: {str(e)}")
                    raise

        except Exception as e:
            logger.error(f"Error handling supplier delivery: {str(e)}", exc_info=True)
            raise

    def _send_pre_uploaded_products(
        self, user_id: int, order_id: str, products: list[Dict[str, Any]]
    ) -> str:
        """
        Send pre-uploaded products to user via Telegram and save to file.

        Sends two messages: (1) text content of the delivery file, (2) the .txt file itself.

        Args:
            user_id: Telegram user ID
            order_id: Order ID
            products: List of product data dictionaries

        Returns:
            delivery_content: The product data lines (without file header), for use in
            the admin ORDER_PAID notification.
        """
        if not self.bot:
            raise RuntimeError(f"Cannot send products: bot instance is None for order {order_id}")

        try:
            logger.info(f"=== Sending pre-uploaded products for order {order_id} ===")
            logger.info(f"User ID: {user_id}, Total products to deliver: {len(products)}")
            logger.info(f"Bot instance available: {self.bot is not None}")

            # Create file content with timestamp and header
            delivery_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            system_name = os.getenv("SYSTEM_NAME", "MUATAIKHOANPRO")
            file_header = (
                f"================\n"
                f"{system_name}\n"
                f"Order ID: {order_id}\n"
                f"Delivered: {delivery_time}\n"
                f"User ID: {user_id}\n"
                f"================\n\n"
            )

            # Build product data lines separately so we can include them in the notification
            product_lines = ""
            for product in products:
                logger.info(f"Product: {product}")
                product_data = product.get("data", {})
                logger.info(f"Product data: {product_data}")

                # Format product data (could be account credentials, codes, etc.)
                if isinstance(product_data, dict) and product_data:
                    # Check if it's our wrapper dict for plain text
                    if "delivery_data" in product_data and len(product_data) == 1:
                        raw_text = product_data["delivery_data"]
                        product_lines += f"{raw_text}\n"
                    elif "value" in product_data and len(product_data) == 1:
                        product_lines += f"{product_data['value']}\n"
                    else:
                        for key, value in product_data.items():
                            product_lines += f"{key}: {value}\n"
                elif isinstance(product_data, dict) and not product_data:
                    product_id = product.get('id', 'N/A')
                    product_lines += f"[Product ID: {product_id} - No delivery data available]\n"
                else:
                    product_lines += f"{str(product_data)}\n"

            file_content = file_header + product_lines
            logger.info(f"File content:\n{file_content}")

            # Save to file
            file_path = DELIVERY_FILES_DIR / f"{order_id}.txt"
            try:
                if file_path.exists():
                    logger.warning(f"Delivery file already exists for order {order_id}. This should not happen due to order status check.")
                else:
                    file_path.write_text(file_content, encoding='utf-8')
                    logger.info(f"Delivery data saved to file: {file_path}")
            except PermissionError as e:
                logger.warning(f"Could not save delivery data to file: {str(e)}")
            except Exception as e:
                logger.error(f"Error saving delivery data to file: {str(e)}")

            sent_ok = False
            try:
                # Message 1: Send delivery content as plain text
                # Telegram text message limit is 4096 chars; truncate if needed
                MAX_TEXT_LEN = 4096
                text_to_send = file_content if len(file_content) <= MAX_TEXT_LEN else file_content[:MAX_TEXT_LEN - 3] + "..."
                logger.info(f"Sending delivery content as text message to user {user_id}")
                run_async(self.bot.send_message(
                    chat_id=user_id,
                    text=text_to_send,
                ))
                logger.info(f"✓ Delivery text message sent to user {user_id}")

                # Message 2: Send delivery file as document
                if file_path.exists():
                    logger.info(f"Sending delivery file to user {user_id} for order {order_id}")
                    logger.info(f"File path: {file_path}, File size: {file_path.stat().st_size} bytes")

                    with open(file_path, 'rb') as f:
                        file_data = f.read()

                    file_obj = BytesIO(file_data)
                    file_obj.name = f"Order_{order_id}.txt"

                    logger.info(f"Calling bot.send_document for user {user_id}")
                    result = run_async(self.bot.send_document(
                        chat_id=user_id,
                        document=file_obj,
                        filename=f"Order_{order_id}.txt",
                        caption=f"📄 Delivery details for order {order_id}"
                    ))
                    if not result:
                        raise RuntimeError("bot.send_document returned no result")
                    logger.info(f"✓ Delivery file sent successfully to user {user_id}. Message ID: {result.message_id}")
                    sent_ok = True
                else:
                    logger.error(f"Delivery file does not exist at {file_path}. Cannot send to user.")
                    raise RuntimeError("Delivery file does not exist; cannot send")
            except TelegramError as e:
                logger.error(f"Telegram error sending delivery to user {user_id}: {str(e)}", exc_info=True)
                raise
            except Exception as e:
                logger.error(f"Failed to send delivery to user {user_id}: {str(e)}", exc_info=True)
                raise

            # Delete the delivery file only after successful delivery
            if sent_ok:
                try:
                    if file_path.exists():
                        file_path.unlink()
                        logger.info(f"✓ Delivery file deleted after successful delivery: {file_path}")
                except Exception as e:
                    logger.warning(f"Could not delete delivery file: {str(e)}")

            return product_lines.strip()

        except TelegramError as e:
            logger.error(f"Failed to send pre-uploaded products: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error in _send_pre_uploaded_products: {str(e)}", exc_info=True)
            raise


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
        logger.info("Global customer bot not set, attempting to create from environment variables...")
        _global_bot = _create_bot_from_env()
        if _global_bot:
            logger.info("✓ Customer bot created successfully from environment")
        else:
            logger.warning("⚠ Failed to create customer bot from environment. Delivery may fail.")

    if _global_supplier_bot is None:
        logger.info("Global supplier bot not set, attempting to create from environment variables...")
        _global_supplier_bot = _create_supplier_bot_from_env()
        if _global_supplier_bot:
            logger.info("✓ Supplier bot created successfully from environment")
        else:
            logger.warning("⚠ Failed to create supplier bot from environment. Supplier notifications may fail.")

    logger.info(f"IPN processor created: customer_bot={'available' if _global_bot else 'None'}, supplier_bot={'available' if _global_supplier_bot else 'None'}")
    return IPNOrderProcessor(bot=_global_bot, supplier_bot=_global_supplier_bot)
