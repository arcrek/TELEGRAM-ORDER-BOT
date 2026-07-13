"""
Message handlers for the supplier bot.
Handles supplier replies to order notifications.
"""
import logging
from typing import Dict, Any
from telegram import Update
from telegram.ext import ContextTypes
from src.database.connection import get_session_factory
from src.database.services.supplier_service import SupplierService
from src.database.services.order_service import OrderService
from src.database.models.supplier_order import SupplierOrder
from src.database.models.enums import SupplierOrderStatus, OrderStatus
from src.ipn import get_global_customer_bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


def parse_product_data(text: str) -> Dict[str, Any]:
    """
    Parse product data from supplier's reply text.
    Supports formats like:
    - "username: user123\npassword: pass456"
    - "key1: value1\nkey2: value2"
    - Simple text (will be stored as "data" field)
    
    Args:
        text: Supplier's reply text
        
    Returns:
        Dictionary with parsed product data
    """
    data = {}
    lines = text.strip().split("\n")
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Try to parse "key: value" format
        if ":" in line:
            parts = line.split(":", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                if key and value:
                    data[key] = value
        else:
            # If no colon, treat as simple text
            if "data" not in data:
                data["data"] = []
            data["data"].append(line)
    
    # If we have a list of simple text lines, join them
    if "data" in data and isinstance(data["data"], list):
        data["data"] = "\n".join(data["data"])
    
    # If no structured data found, store entire text as "data"
    if not data:
        data["data"] = text.strip()
    
    return data


async def handle_supplier_reply(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle supplier's reply to an order notification.
    Parses product data and forwards it to the customer.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    user = update.effective_user
    message = update.message
    
    # Check if this is a reply to a message
    if not message.reply_to_message:
        return  # Not a reply, ignore
    
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        supplier_service = SupplierService(session)
        order_service = OrderService(session)
        
        # Check if user is a registered supplier
        supplier = supplier_service.get_supplier_by_telegram_id(user.id)
        if not supplier or not supplier.is_active:
            await message.reply_text(
                "❌ You are not registered as a supplier.\n"
                "Use /register to register first."
            )
            return
        
        # Get the replied-to message ID
        replied_message_id = message.reply_to_message.message_id
        
        # Find supplier order by notification message ID
        supplier_order = (
            session.query(SupplierOrder)
            .filter_by(
                supplier_id=supplier.id,
                notification_message_id=replied_message_id,
            )
            .first()
        )
        
        if not supplier_order:
            await message.reply_text(
                "❌ This message is not associated with any order.\n"
                "Please reply directly to an order notification."
            )
            return
        
        # Check if already delivered
        if supplier_order.status == SupplierOrderStatus.DELIVERED:
            await message.reply_text(
                "⚠️ This order has already been delivered.\n"
                "The customer has already received the product."
            )
            return
        
        # Parse product data from supplier's message
        product_data = parse_product_data(message.text or "")
        
        if not product_data:
            await message.reply_text(
                "❌ Could not parse product data from your message.\n\n"
                "Please provide product data in one of these formats:\n"
                "• username: user123\n  password: pass456\n"
                "• key1: value1\n  key2: value2\n"
                "• Or any text format"
            )
            return
        
        # Get the order
        order = order_service.get_order_by_id(supplier_order.order_id)
        if not order:
            await message.reply_text("❌ Order not found.")
            return
        
        # Update supplier order status
        supplier_order.status = SupplierOrderStatus.DELIVERED
        supplier_order.supplier_response_message_id = message.message_id
        session.commit()
        
        # Update main order status if all supplier orders are delivered
        all_supplier_orders = (
            session.query(SupplierOrder)
            .filter_by(order_id=order.id)
            .all()
        )
        if all(so.status == SupplierOrderStatus.DELIVERED for so in all_supplier_orders):
            order_service.update_order_status(order.id, OrderStatus.DELIVERED)
        
        # Format product data for customer
        if isinstance(product_data, dict):
            if len(product_data) == 1 and "data" in product_data:
                # Simple text format
                product_message = f"✅ Your product is ready!\n\n📦 Order ID: {order.id}\n\n{product_data['data']}"
            else:
                # Structured format
                product_lines = [f"✅ Your product is ready!\n\n📦 Order ID: {order.id}\n"]
                for key, value in product_data.items():
                    product_lines.append(f"{key}: {value}")
                product_message = "\n".join(product_lines)
        else:
            product_message = f"✅ Your product is ready!\n\n📦 Order ID: {order.id}\n\n{str(product_data)}"
        
        # Send product data to customer
        # Get the customer bot instance from global or context
        customer_bot = get_global_customer_bot() or context.bot_data.get("customer_bot")
        if customer_bot:
            try:
                customer_bot.send_message(
                    chat_id=order.user_id,
                    text=product_message,
                )
                await message.reply_text(
                    f"✅ Product data sent to customer!\n\n"
                    f"Order ID: {order.id}\n"
                    f"Customer notified."
                )
                logger.info(
                    f"Supplier {supplier.id} delivered product for order {order.id}"
                )
            except TelegramError as e:
                logger.error(f"Failed to send product to customer: {str(e)}")
                await message.reply_text(
                    "❌ Failed to send product to customer.\n"
                    "Please try again or contact support."
                )
        else:
            logger.warning("Customer bot instance not available in context")
            await message.reply_text(
                "⚠️ Customer bot not configured. Product data saved but not sent.\n"
                "Please contact support."
            )
            
    except Exception as e:
        logger.error(f"Error handling supplier reply: {str(e)}", exc_info=True)
        await message.reply_text(
            "❌ An error occurred while processing your reply.\n"
            "Please try again or contact support."
        )
        session.rollback()
    finally:
        session.close()
