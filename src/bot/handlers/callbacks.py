"""
Callback query handlers for the Telegram bot.
"""
import base64
import logging
from io import BytesIO
from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.database.connection import get_session_factory
from src.database.services.product_service import ProductService
from src.database.services.variation_service import VariationService
from src.database.services.order_service import OrderService
from src.bot.messages.product_formatter import ProductFormatter
from src.bot.messages.product_detail_formatter import ProductDetailFormatter
from src.bot.messages.order_confirmation_formatter import OrderConfirmationFormatter
from src.bot.states.state_manager import StateManager
from src.database.models.enums import DeliveryType

logger = logging.getLogger(__name__)


# Global state manager instance
state_manager = StateManager()


def get_actual_stock(variation, product, variation_service: VariationService) -> int:
    """
    Get actual available stock for a variation based on product delivery type.
    
    Args:
        variation: ProductVariation instance
        product: Product instance
        variation_service: VariationService instance
    
    Returns:
        Actual available stock count
    """
    if product.delivery_type == DeliveryType.PRE_UPLOADED:
        # For PRE_UPLOADED products, calculate from available pre-uploaded products
        return variation_service.calculate_stock_from_pre_uploaded(variation.id)
    else:
        # For SUPPLIER_BASED products, use the stock field directly
        return variation.stock


async def handle_page_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle page navigation callback (next/prev page).
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    query = update.callback_query
    await query.answer()
    
    # Parse page number from callback data (format: "page_2")
    page = int(query.data.split("_")[1])
    user_id = query.from_user.id
    
    # Update user state
    state_manager.update_user_state(user_id, current_page=page)
    
    # Get products for the page
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        product_service = ProductService(session)
        formatter = ProductFormatter()
        
        # Get products for the page
        products = product_service.list_products(page=page, per_page=formatter.ITEMS_PER_PAGE, only_active=True)
        total_count = product_service.get_total_count(only_active=True)
        total_pages = formatter.calculate_total_pages(total_count)
        
        # Format message and keyboard
        message = formatter.format_product_list(products, page, total_pages)
        keyboard = formatter.create_product_keyboard(products, page, total_pages)
        
        # Update message
        await query.edit_message_text(message, reply_markup=keyboard)
    finally:
        session.close()


async def handle_product_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle product selection callback.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    query = update.callback_query
    await query.answer()
    
    # Parse product ID from callback data (format: "product_prod_1")
    product_id = query.data.replace("product_", "")
    user_id = query.from_user.id
    
    # Update user state
    state_manager.update_user_state(user_id, selected_product_id=product_id)
    
    # Get product details
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        product_service = ProductService(session)
        variation_service = VariationService(session)
        formatter = ProductDetailFormatter()
        
        # Get product
        product = product_service.get_product_by_id(product_id)
        if not product:
            await query.edit_message_text("❌ Product not found.")
            return
        
        # Get variations
        variations = variation_service.list_variations_by_product(product_id, only_active=True)
        
        # Calculate actual stock based on delivery type and update variation objects
        total_stock = 0
        for variation in variations:
            actual_stock = get_actual_stock(variation, product, variation_service)
            variation.stock = actual_stock  # Override with actual stock
            total_stock += actual_stock
        
        # Get current page from state (for back button)
        user_state = state_manager.get_user_state(user_id)
        current_page = user_state.current_page if user_state else 1
        
        # Format message and keyboard
        message = formatter.format_product_detail(product, variations, total_stock)
        keyboard = formatter.create_product_detail_keyboard(product_id, current_page, variations)
        
        # Update message
        await query.edit_message_text(message, reply_markup=keyboard)
    finally:
        session.close()


async def handle_variation_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle variation selection callback.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    query = update.callback_query
    await query.answer()
    
    # Parse variation ID from callback data (format: "variation_var_1")
    variation_id = query.data.replace("variation_", "")
    user_id = query.from_user.id
    
    # Get variation and product
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        variation_service = VariationService(session)
        product_service = ProductService(session)
        formatter = OrderConfirmationFormatter()
        
        # Get variation
        variation = variation_service.get_variation_by_id(variation_id)
        if not variation:
            await query.edit_message_text("❌ Variation not found.")
            return
        
        # Get product
        product = product_service.get_product_by_id(variation.product_id)
        if not product:
            await query.edit_message_text("❌ Product not found.")
            return
        
        # Get actual stock based on delivery type
        actual_stock = get_actual_stock(variation, product, variation_service)
        variation.stock = actual_stock  # Override with actual stock
        
        # Update user state
        state_manager.update_user_state(
            user_id,
            selected_variation_id=variation_id,
            quantity=1,  # Default quantity
        )
        
        # Format order confirmation
        quantity = 1
        message = formatter.format_order_confirmation(product, variation, quantity)
        keyboard = formatter.create_quantity_keyboard(variation_id, quantity, actual_stock)
        
        # Update message
        await query.edit_message_text(message, reply_markup=keyboard)
    finally:
        session.close()


async def handle_quantity_adjustment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle quantity adjustment callback (+1, +5, -1, -5).
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    query = update.callback_query
    await query.answer()
    
    # Parse adjustment from callback data (format: "qty_var_1_+1" or "qty_alight_12m_1_+1")
    # The last part is always the adjustment (+1, +5, -1, -5)
    # Everything between "qty_" and the last part is the variation_id
    parts = query.data.split("_")
    adjustment = parts[-1]  # Last part: +1, +5, -1, -5
    variation_id = "_".join(parts[1:-1])  # Everything between "qty" and adjustment
    user_id = query.from_user.id
    
    # Get user state
    user_state = state_manager.get_user_state(user_id)
    if not user_state or not user_state.selected_variation_id:
        await query.edit_message_text("❌ Please select a variation first.")
        return
    
    # Get variation
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        variation_service = VariationService(session)
        product_service = ProductService(session)
        formatter = OrderConfirmationFormatter()
        
        variation = variation_service.get_variation_by_id(variation_id)
        if not variation:
            await query.edit_message_text("❌ Variation not found.")
            return
        
        product = product_service.get_product_by_id(variation.product_id)
        if not product:
            await query.edit_message_text("❌ Product not found.")
            return
        
        # Get actual stock based on delivery type
        actual_stock = get_actual_stock(variation, product, variation_service)
        variation.stock = actual_stock  # Override with actual stock
        
        # Calculate new quantity
        current_quantity = user_state.quantity
        adjustment_value = int(adjustment)
        new_quantity = current_quantity + adjustment_value
        
        # Validate quantity
        new_quantity = formatter.validate_quantity(new_quantity, actual_stock)
        
        # Update state
        state_manager.update_user_state(user_id, quantity=new_quantity)
        
        # Format updated order confirmation
        message = formatter.format_order_confirmation(product, variation, new_quantity)
        keyboard = formatter.create_quantity_keyboard(variation_id, new_quantity, actual_stock)
        
        # Update message
        await query.edit_message_text(message, reply_markup=keyboard)
    finally:
        session.close()


async def handle_refresh_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle refresh product callback.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    query = update.callback_query
    await query.answer("🔄 Refreshing...")
    
    user_id = query.from_user.id
    user_state = state_manager.get_user_state(user_id)
    
    if not user_state or not user_state.selected_product_id:
        await query.edit_message_text("❌ No product selected.")
        return
    
    # Temporarily store product_id for handle_product_selection
    product_id = user_state.selected_product_id
    
    # Get product details
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        product_service = ProductService(session)
        variation_service = VariationService(session)
        formatter = ProductDetailFormatter()
        
        # Get product
        product = product_service.get_product_by_id(product_id)
        if not product:
            await query.edit_message_text("❌ Product not found.")
            return
        
        # Get variations
        variations = variation_service.list_variations_by_product(product_id, only_active=True)
        
        # Calculate actual stock based on delivery type and update variation objects
        total_stock = 0
        for variation in variations:
            actual_stock = get_actual_stock(variation, product, variation_service)
            variation.stock = actual_stock  # Override with actual stock
            total_stock += actual_stock
        
        # Get current page from state (for back button)
        current_page = user_state.current_page if user_state else 1
        
        # Format message and keyboard
        message = formatter.format_product_detail(product, variations, total_stock)
        keyboard = formatter.create_product_detail_keyboard(product_id, current_page, variations)
        
        # Update message
        await query.edit_message_text(message, reply_markup=keyboard)
    finally:
        session.close()


async def handle_back_to_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle back to list callback.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_state = state_manager.get_user_state(user_id)
    
    # Get current page from state
    current_page = user_state.current_page if user_state else 1
    
    # Show product list for that page
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        product_service = ProductService(session)
        formatter = ProductFormatter()
        
        products = product_service.list_products(page=current_page, per_page=formatter.ITEMS_PER_PAGE, only_active=True)
        total_count = product_service.get_total_count(only_active=True)
        total_pages = formatter.calculate_total_pages(total_count)
        
        message = formatter.format_product_list(products, current_page, total_pages)
        keyboard = formatter.create_product_keyboard(products, current_page, total_pages)
        
        await query.edit_message_text(message, reply_markup=keyboard)
    finally:
        session.close()


async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle payment callback - create order and payment URL.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    query = update.callback_query
    await query.answer("💳 Processing payment...")
    
    # Parse variation ID from callback data (format: "payment_var_1" or "payment_alight_12m_1")
    variation_id = query.data.replace("payment_", "")
    user_id = query.from_user.id
    
    # Get user state
    user_state = state_manager.get_user_state(user_id)
    if not user_state or not user_state.selected_variation_id:
        await query.edit_message_text("❌ Please select a variation first.")
        return
    
    if user_state.selected_variation_id != variation_id:
        await query.edit_message_text("❌ Variation mismatch. Please try again.")
        return
    
    quantity = user_state.quantity or 1
    
    # Get services
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        order_service = OrderService(session)
        variation_service = VariationService(session)
        product_service = ProductService(session)
        
        # Validate stock one more time
        if not order_service.validate_stock(variation_id, quantity):
            variation = variation_service.get_variation_by_id(variation_id)
            if variation:
                product = product_service.get_product_by_id(variation.product_id)
                if product:
                    actual_stock = get_actual_stock(variation, product, variation_service)
                    await query.edit_message_text(
                        f"❌ Insufficient stock. Available: {actual_stock}, Requested: {quantity}"
                    )
                else:
                    await query.edit_message_text("❌ Product not found.")
            else:
                await query.edit_message_text("❌ Variation not found.")
            return
        
        # Create order
        try:
            order = order_service.create_order(
                user_id=user_id,
                variation_id=variation_id,
                quantity=quantity,
            )
        except ValueError as e:
            await query.edit_message_text(f"❌ {str(e)}")
            return
        
        # Create payment URL
        try:
            import os
            import sys
            
            # Try to import config - handle both direct and Docker execution
            try:
                from config.config import (
                    PAY2S_ENDPOINT,
                    PARTNER_CODE,
                    ACCESS_KEY,
                    SECRET_KEY,
                    DEFAULT_BANK_ACCOUNTS,
                )
            except ModuleNotFoundError:
                # Fallback: Use environment variables directly
                PAY2S_ENDPOINT = os.getenv("PAY2S_ENDPOINT", "...")
                PARTNER_CODE = os.getenv("PAY2S_PARTNER_CODE", "...")
                ACCESS_KEY = os.getenv("PAY2S_ACCESS_KEY", "...")
                SECRET_KEY = os.getenv("PAY2S_SECRET_KEY", "...")
                DEFAULT_BANK_ACCOUNTS = os.getenv("DEFAULT_BANK_ACCOUNTS", "[]")
                if isinstance(DEFAULT_BANK_ACCOUNTS, str):
                    import json
                    try:
                        DEFAULT_BANK_ACCOUNTS = json.loads(DEFAULT_BANK_ACCOUNTS)
                    except:
                        DEFAULT_BANK_ACCOUNTS = []
            
            from src.pay2s import create_payment
            
            # Validate PAY2S_ENDPOINT
            if not PAY2S_ENDPOINT or PAY2S_ENDPOINT == '...' or not PAY2S_ENDPOINT.startswith(('http://', 'https://')):
                error_msg = (
                    "❌ Payment configuration error.\n\n"
                    "The Pay2S endpoint is not configured correctly.\n"
                    "Please set PAY2S_ENDPOINT environment variable or update config/config.py\n\n"
                    f"Current value: {repr(PAY2S_ENDPOINT)}"
                )
                await query.answer("Payment configuration error", show_alert=True)
                await query.edit_message_text(error_msg)
                logger.error(f"Invalid PAY2S_ENDPOINT: {repr(PAY2S_ENDPOINT)}")
                return
            
            # Validate other required config
            if not ACCESS_KEY or ACCESS_KEY == '...' or not SECRET_KEY or SECRET_KEY == '...':
                error_msg = (
                    "❌ Payment configuration error.\n\n"
                    "ACCESS_KEY or SECRET_KEY is not configured correctly.\n"
                    "Please update config/config.py\n"
                )
                await query.answer("Payment configuration error", show_alert=True)
                await query.edit_message_text(error_msg)
                logger.error("Invalid ACCESS_KEY or SECRET_KEY in payment config")
                return
            
            # Validate bank accounts are configured
            if not DEFAULT_BANK_ACCOUNTS or len(DEFAULT_BANK_ACCOUNTS) == 0:
                error_msg = (
                    "❌ Payment configuration error.\n\n"
                    "No bank accounts configured.\n"
                    "Please configure DEFAULT_BANK_ACCOUNTS in config/config.py\n"
                )
                await query.answer("Payment configuration error", show_alert=True)
                await query.edit_message_text(error_msg)
                logger.error("DEFAULT_BANK_ACCOUNTS not configured")
                return
            
            # Get IPN URL from environment or use default
            ipn_url = os.getenv("IPN_URL", f"http://localhost:{os.getenv('IPN_PORT', '5001')}/ipn")
            redirect_url = os.getenv("REDIRECT_URL", "https://t.me/your_bot")
            
            # Create order info (10-32 chars, alphanumeric only)
            # Format: MTK + order_id (matching Pay2S expected format)
            order_info = f"MTK_{order.id}"[:32]
            
            # Generate unique request_id using timestamp (as per Pay2S API sample)
            import time
            request_id = str(int(time.time() * 1000))  # milliseconds timestamp
            
            logger.info(f"Creating payment: endpoint={PAY2S_ENDPOINT}, order_id={order.id}, amount={order.total_amount}, order_info={order_info}, request_id={request_id}")
            logger.debug(f"Bank accounts: {DEFAULT_BANK_ACCOUNTS}")
            logger.debug(f"IPN URL: {ipn_url}, Redirect URL: {redirect_url}")
            
            # Create payment
            payment_response = create_payment(
                endpoint=PAY2S_ENDPOINT,
                access_key=ACCESS_KEY,
                secret_key=SECRET_KEY,
                partner_code=PARTNER_CODE,
                amount=order.total_amount,
                order_id=order.id,
                order_info=order_info,
                redirect_url=redirect_url,
                ipn_url=ipn_url,
                bank_accounts=DEFAULT_BANK_ACCOUNTS,
                request_id=request_id,
            )
            
            logger.debug(f"Payment response: {payment_response}")
            
            # Extract payment URL and QR code
            if payment_response.get("resultCode") == 0 and payment_response.get("payUrl"):
                payment_url = payment_response["payUrl"]
                
                # Update order with transaction ID if available
                transaction_id = payment_response.get("transId")
                if transaction_id:
                    order_service.update_order_status(
                        order.id,
                        order.status,  # Keep current status
                        payment_transaction_id=transaction_id,
                    )
                
                # Update user state
                state_manager.update_user_state(user_id, pending_order_id=order.id)
                
                # Prepare payment message with auto-cancel notification
                payment_message = (
                    f"✅ Order created successfully!\n\n"
                    f"📦 Order ID: {order.id}\n"
                    f"💰 Total: {order.total_amount:,} VND\n\n"
                    f"💳 Scan QR code below to complete payment\n\n"
                    f"⏰ This order will be automatically cancelled if payment is not completed within 30 minutes."
                )
                
                # Extract QR code from response
                qr_code_data = None
                qr_list = payment_response.get("qrList", [])
                if qr_list and len(qr_list) > 0:
                    qr_code = qr_list[0].get("qrCode")
                    if qr_code and qr_code.startswith("data:image/png;base64,"):
                        # Extract base64 data
                        base64_data = qr_code.replace("data:image/png;base64,", "")
                        try:
                            qr_code_data = base64.b64decode(base64_data)
                        except Exception as e:
                            logger.warning(f"Failed to decode QR code: {str(e)}")
                            qr_code_data = None
                
                # Send payment message with QR code if available
                if qr_code_data:
                    # Create BytesIO object from image data
                    qr_image = BytesIO(qr_code_data)
                    qr_image.name = "qr_code.png"
                    
                    # Create cancel button inline keyboard
                    cancel_keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel_order_{order.id}")]
                    ])
                    
                    # Edit the callback message first
                    await query.edit_message_text(payment_message)
                    
                    # Send QR code as photo with cancel button
                    sent_message = await context.bot.send_photo(
                        chat_id=user_id,
                        photo=InputFile(qr_image, filename="qr_code.png"),
                        caption=(
                            f"📦 Order ID: {order.id}\n"
                            f"💰 Total: {order.total_amount:,} VND\n\n"
                            f"⏰ Auto-cancels in 30 minutes if unpaid"
                        ),
                        reply_markup=cancel_keyboard
                    )
                    
                    # Store message ID for later deletion
                    state_manager.update_user_state(user_id, payment_message_id=sent_message.message_id)
                else:
                    # Fallback to text message with payment URL if QR code not available
                    payment_message += f"\n\n🔗 Payment link:\n{payment_url}"
                    # Create cancel button for text message too
                    cancel_keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel_order_{order.id}")]
                    ])
                    edited_message = await query.edit_message_text(payment_message, reply_markup=cancel_keyboard)
                    
                    # Store message ID for later deletion (use edited message ID)
                    if edited_message:
                        state_manager.update_user_state(user_id, payment_message_id=edited_message.message_id)
            else:
                error_msg = payment_response.get("message", "Unknown error")
                await query.edit_message_text(f"❌ Payment creation failed: {error_msg}")
                logger.error(f"Payment creation failed: {payment_response}")
        
        except ValueError as e:
            # Config validation errors
            error_msg = str(e)
            logger.error(f"Payment configuration error: {error_msg}")
            await query.edit_message_text(f"❌ Configuration error: {error_msg}")
        except Exception as e:
            logger.error(f"Error creating payment: {str(e)}", exc_info=True)
            # Provide more helpful error message
            error_detail = str(e)
            if "Connection" in error_detail or "timeout" in error_detail.lower():
                error_message = (
                    "❌ Payment service connection error.\n\n"
                    "Unable to connect to payment gateway.\n"
                    "Please check your internet connection and try again."
                )
            elif "Invalid" in error_detail:
                error_message = f"❌ Invalid payment request: {error_detail}"
            else:
                error_message = "❌ Error creating payment. Please try again later."
            await query.edit_message_text(error_message)
    
    finally:
        session.close()


async def handle_cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle cancel order callback - cancel a pending order.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    query = update.callback_query
    await query.answer("Processing cancellation...")
    
    # Parse order ID from callback data (format: "cancel_order_abc12345")
    order_id = query.data.replace("cancel_order_", "")
    user_id = query.from_user.id
    
    # Get services
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        order_service = OrderService(session)
        
        # Get order and validate ownership
        order = order_service.get_order_by_id(order_id)
        if not order:
            await query.answer("❌ Order not found.", show_alert=True)
            return
        
        if order.user_id != user_id:
            await query.answer("❌ You can only cancel your own orders.", show_alert=True)
            return
        
        # Cancel the order
        try:
            cancelled_order = order_service.cancel_order(order_id)
            
            # Send confirmation message
            confirmation_message = (
                f"✅ Order cancelled successfully!\n\n"
                f"📦 Order ID: {cancelled_order.id}\n"
                f"💰 Amount: {cancelled_order.total_amount:,} VND\n\n"
                f"Your order has been cancelled. You can place a new order anytime."
            )
            
            # Delete the QR payment message
            user_state = state_manager.get_user_state(user_id)
            if user_state and user_state.payment_message_id:
                try:
                    await context.bot.delete_message(
                        chat_id=user_id,
                        message_id=user_state.payment_message_id
                    )
                    logger.info(f"Deleted payment message {user_state.payment_message_id} for cancelled order {order_id}")
                except Exception as e:
                    logger.warning(f"Could not delete payment message: {str(e)}")
            
            # Try to edit the message to remove the cancel button (if it's a callback query message)
            try:
                await query.edit_message_caption(
                    caption=(
                        f"📦 Order ID: {cancelled_order.id}\n"
                        f"💰 Total: {cancelled_order.total_amount:,} VND\n\n"
                        f"❌ Order cancelled"
                    ),
                    reply_markup=None
                )
            except Exception as e:
                # If editing fails (e.g., message already edited), just send new message
                logger.warning(f"Could not edit message: {str(e)}")
            
            # Send confirmation message
            await context.bot.send_message(
                chat_id=user_id,
                text=confirmation_message
            )
            
            # Clear pending order and payment message from user state
            state_manager.update_user_state(user_id, pending_order_id=None, payment_message_id=None)
            
        except ValueError as e:
            # Order cannot be cancelled (not PENDING)
            await query.answer(f"❌ {str(e)}", show_alert=True)
            logger.warning(f"Cannot cancel order {order_id}: {str(e)}")
    
    except Exception as e:
        logger.error(f"Error cancelling order: {str(e)}", exc_info=True)
        await query.answer("❌ Error cancelling order. Please try again later.", show_alert=True)
    
    finally:
        session.close()


async def handle_language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle language selection callback.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    query = update.callback_query
    await query.answer()
    
    # Parse language from callback data (format: "lang_en" or "lang_vi")
    language_code = query.data.replace("lang_", "")
    
    if language_code not in ["en", "vi"]:
        await query.answer("❌ Invalid language selection.", show_alert=True)
        return
    
    user_id = query.from_user.id
    
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        from src.database.services.user_preference_service import UserPreferenceService
        from src.bot.utils.language import t
        
        preference_service = UserPreferenceService(session)
        preference_service.set_user_language(user_id, language_code)
        
        # Get language display name
        lang_display = t('languages.en', update) if language_code == 'en' else t('languages.vi', update)
        
        # Send confirmation message
        confirmation = t('commands.language.changed', update, language=lang_display)
        await query.edit_message_text(confirmation)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error setting language: {str(e)}", exc_info=True)
        await query.answer("❌ Error changing language. Please try again.", show_alert=True)
    finally:
        session.close()

