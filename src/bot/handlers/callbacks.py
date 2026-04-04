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
from src.database.services.order_notification_service import OrderNotificationService
from src.database.services.bot_ui_settings_service import BotUiSettingsService
from src.bot.messages.product_formatter import ProductFormatter
from src.bot.messages.product_detail_formatter import ProductDetailFormatter
from src.bot.messages.order_confirmation_formatter import OrderConfirmationFormatter
from src.bot.states.state_manager import StateManager
from src.database.models.enums import DeliveryType

logger = logging.getLogger(__name__)


# Global state manager instance
state_manager = StateManager()


def _get_bot_selection_prompts(session) -> tuple[str | None, str | None]:
    """Load global custom prompt texts for product/variation selection."""
    service = BotUiSettingsService(session)
    settings = service.get_settings()
    return settings.product_choose_text, settings.variation_choose_text


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


def format_payment_message(order, update, session) -> tuple[str, str]:
    """
    Format payment message with item details and translations.
    
    Args:
        order: Order instance with items
        update: Telegram update for language detection
        session: Database session
    
    Returns:
        Tuple of (full_message, caption_message)
    """
    from src.bot.utils.language import t
    
    # Get translations
    order_created = t('payment.order_created', update) if update else "✅ Order created successfully!"
    scan_qr = t('payment.scan_qr', update) if update else "💳 Scan QR code below to complete payment"
    auto_cancel = t('payment.auto_cancel_30min', update) if update else "⏰ This order will be automatically cancelled if payment is not completed within 30 minutes."
    auto_cancel_short = t('payment.auto_cancel_short', update) if update else "⏰ Auto-cancels in 30 minutes if unpaid"
    product_label = t('payment.product_label', update) if update else "📌 Product"
    variation_label = t('payment.variation_label', update) if update else "➕ Type"
    quantity_label = t('payment.quantity_label', update) if update else "👉 Order quantity"
    total_amount_label = t('payment.total_amount_label', update) if update else "💰 Total Amount"
    
    lines = [order_created, ""]
    lines.append(f"📦 Order ID: {order.id}")
    
    # Format item details
    product_service = ProductService(session)
    variation_service = VariationService(session)
    
    for item in order.items:
        # Get product and variation info
        product = product_service.get_product_by_id(item.product_id) if item.product_id else None
        variation = variation_service.get_variation_by_id(item.variation_id) if item.variation_id else None
        
        product_name = product.name if product else "N/A"
        variation_name = variation.name if variation else "N/A"
        
        lines.append(f"{product_label}: {product_name}")
        lines.append(f"{variation_label}: {variation_name}")
        
        # Format quantity with bonus
        bonus_qty = item.bonus_quantity or 0
        if bonus_qty > 0:
            qty_with_bonus = t('payment.quantity_with_bonus', update) if update else "x{quantity} (Bonus {bonus})"
            qty_text = qty_with_bonus.format(quantity=item.quantity, bonus=bonus_qty)
        else:
            qty_no_bonus = t('payment.quantity_no_bonus', update) if update else "x{quantity}"
            qty_text = qty_no_bonus.format(quantity=item.quantity)
        
        lines.append(f"{quantity_label}: {qty_text}")
    
    lines.append("")
    lines.append(f"{total_amount_label}: {order.total_amount:,} VND")
    lines.append("")
    lines.append(scan_qr)
    lines.append("")
    lines.append(auto_cancel)
    
    full_message = "\n".join(lines)
    
    # Shorter caption for QR image
    caption_lines = [
        f"📦 Order ID: {order.id}"
    ]
    
    for item in order.items:
        product = product_service.get_product_by_id(item.product_id) if item.product_id else None
        variation = variation_service.get_variation_by_id(item.variation_id) if item.variation_id else None
        
        product_name = product.name if product else "N/A"
        variation_name = variation.name if variation else "N/A"
        
        caption_lines.append(f"{product_label}: {product_name}")
        caption_lines.append(f"{variation_label}: {variation_name}")
        
        bonus_qty = item.bonus_quantity or 0
        if bonus_qty > 0:
            qty_with_bonus = t('payment.quantity_with_bonus', update) if update else "x{quantity} (Bonus {bonus})"
            qty_text = qty_with_bonus.format(quantity=item.quantity, bonus=bonus_qty)
        else:
            qty_no_bonus = t('payment.quantity_no_bonus', update) if update else "x{quantity}"
            qty_text = qty_no_bonus.format(quantity=item.quantity)
        
        caption_lines.append(f"{quantity_label}: {qty_text}")
    
    caption_lines.append(f"{total_amount_label}: {order.total_amount:,} VND")
    caption_lines.append("")
    caption_lines.append(auto_cancel_short)
    
    caption_message = "\n".join(caption_lines)
    
    return full_message, caption_message


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
        product_choose_text, _ = _get_bot_selection_prompts(session)
        
        # Get products for the page
        products = product_service.list_products(page=page, per_page=formatter.ITEMS_PER_PAGE, only_active=True)
        total_count = product_service.get_total_count(only_active=True)
        total_pages = formatter.calculate_total_pages(total_count)
        
        # Format message and keyboard
        message = formatter.format_product_list(
            products,
            page,
            total_pages,
            update,
            product_choose_text=product_choose_text,
        )
        keyboard = formatter.create_product_keyboard(products, page, total_pages, update)
        
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
        _, variation_choose_text = _get_bot_selection_prompts(session)
        
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
        
        # Get bonus texts for variations
        from src.bot.utils.language import get_user_language
        language = get_user_language(update)
        variation_ids = [v.id for v in variations]
        bonus_texts = formatter.get_bonus_texts_for_variations(variation_ids, session, language)
        
        # Get current page from state (for back button)
        user_state = state_manager.get_user_state(user_id)
        current_page = user_state.current_page if user_state else 1
        
        # Format message and keyboard
        message = formatter.format_product_detail(
            product,
            variations,
            total_stock,
            update,
            bonus_texts,
            variation_choose_text=variation_choose_text,
        )
        keyboard = formatter.create_product_detail_keyboard(product_id, current_page, variations, update)
        
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
        
        # Format order confirmation with bonus
        quantity = 1
        from src.bot.utils.language import get_user_language
        language = get_user_language(update)
        bonus_quantity, bonus_label = formatter.get_applicable_bonus(
            variation_id, quantity, actual_stock, session, language
        )
        message = formatter.format_order_confirmation(
            product, variation, quantity, update, bonus_quantity, bonus_label
        )
        keyboard = formatter.create_quantity_keyboard(variation_id, quantity, actual_stock, update)
        
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
        
        # Format updated order confirmation with bonus
        from src.bot.utils.language import get_user_language
        language = get_user_language(update)
        bonus_quantity, bonus_label = formatter.get_applicable_bonus(
            variation_id, new_quantity, actual_stock, session, language
        )
        message = formatter.format_order_confirmation(
            product, variation, new_quantity, update, bonus_quantity, bonus_label
        )
        keyboard = formatter.create_quantity_keyboard(variation_id, new_quantity, actual_stock, update)
        
        # Update message
        await query.edit_message_text(message, reply_markup=keyboard)
    finally:
        session.close()


async def handle_custom_quantity_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle custom quantity button callback - send a prompt for user to input quantity.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    from src.bot.utils.language import t
    
    query = update.callback_query
    await query.answer()
    
    # Parse variation ID from callback data (format: "qty_custom_var_1" or "qty_custom_alight_12m_1")
    # Remove "qty_custom_" prefix to get variation_id
    variation_id = query.data.replace("qty_custom_", "")
    user_id = query.from_user.id
    
    # Get user state
    user_state = state_manager.get_user_state(user_id)
    if not user_state or not user_state.selected_variation_id:
        await query.edit_message_text("❌ Please select a variation first.")
        return
    
    # Get variation to get max stock
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        variation_service = VariationService(session)
        product_service = ProductService(session)
        
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
        
        # Store the order message ID and set waiting flag
        order_message_id = query.message.message_id
        state_manager.update_user_state(
            user_id,
            waiting_for_custom_quantity=True,
            order_message_id=order_message_id,
        )
        
        # Send prompt message
        prompt_text = t('products.order_confirmation.custom_prompt', update, max_stock=actual_stock)
        prompt_message = await context.bot.send_message(
            chat_id=user_id,
            text=prompt_text
        )
        
        # Store the prompt message ID for deletion later
        state_manager.update_user_state(
            user_id,
            custom_quantity_prompt_message_id=prompt_message.message_id,
        )
        
    finally:
        session.close()


async def handle_custom_quantity_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle text input for custom quantity.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    from src.bot.utils.language import t
    
    user_id = update.effective_user.id
    user_state = state_manager.get_user_state(user_id)
    
    # Check if user is waiting for custom quantity input
    if not user_state or not user_state.waiting_for_custom_quantity:
        return  # Not waiting for input, ignore
    
    if not user_state.selected_variation_id:
        return  # No variation selected
    
    # Try to parse the quantity
    text = update.message.text.strip()
    
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        variation_service = VariationService(session)
        product_service = ProductService(session)
        formatter = OrderConfirmationFormatter()
        
        variation = variation_service.get_variation_by_id(user_state.selected_variation_id)
        if not variation:
            await update.message.reply_text("❌ Variation not found.")
            return
        
        product = product_service.get_product_by_id(variation.product_id)
        if not product:
            await update.message.reply_text("❌ Product not found.")
            return
        
        # Get actual stock based on delivery type
        actual_stock = get_actual_stock(variation, product, variation_service)
        variation.stock = actual_stock  # Override with actual stock for display
        
        # Try to parse the quantity
        try:
            quantity = int(text)
        except ValueError:
            # Invalid input - not a number
            invalid_msg = t('products.order_confirmation.custom_invalid', update, max_stock=actual_stock)
            await update.message.reply_text(invalid_msg)
            return
        
        # Validate quantity range
        if quantity < 1 or quantity > actual_stock:
            invalid_msg = t('products.order_confirmation.custom_invalid', update, max_stock=actual_stock)
            await update.message.reply_text(invalid_msg)
            return
        
        # Valid quantity - update state
        state_manager.update_user_state(
            user_id,
            quantity=quantity,
            waiting_for_custom_quantity=False,
        )
        
        # Delete the prompt message
        if user_state.custom_quantity_prompt_message_id:
            try:
                await context.bot.delete_message(
                    chat_id=user_id,
                    message_id=user_state.custom_quantity_prompt_message_id
                )
            except Exception as e:
                logger.warning(f"Could not delete prompt message: {str(e)}")
        
        # Delete the user's input message
        try:
            await update.message.delete()
        except Exception as e:
            logger.warning(f"Could not delete user input message: {str(e)}")
        
        # Update the order confirmation message with bonus
        if user_state.order_message_id:
            from src.bot.utils.language import get_user_language
            language = get_user_language(update)
            bonus_quantity, bonus_label = formatter.get_applicable_bonus(
                user_state.selected_variation_id, quantity, actual_stock, session, language
            )
            message = formatter.format_order_confirmation(
                product, variation, quantity, update, bonus_quantity, bonus_label
            )
            keyboard = formatter.create_quantity_keyboard(
                user_state.selected_variation_id, quantity, actual_stock, update
            )
            
            try:
                await context.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=user_state.order_message_id,
                    text=message,
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.warning(f"Could not edit order message: {str(e)}")
                # Fallback: send a new message
                await context.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    reply_markup=keyboard
                )
        
        # Clear the prompt message ID from state
        state_manager.update_user_state(
            user_id,
            custom_quantity_prompt_message_id=None,
        )
        
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
        _, variation_choose_text = _get_bot_selection_prompts(session)
        
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
        
        # Get bonus texts for variations
        from src.bot.utils.language import get_user_language
        language = get_user_language(update)
        variation_ids = [v.id for v in variations]
        bonus_texts = formatter.get_bonus_texts_for_variations(variation_ids, session, language)
        
        # Get current page from state (for back button)
        current_page = user_state.current_page if user_state else 1
        
        # Format message and keyboard
        message = formatter.format_product_detail(
            product,
            variations,
            total_stock,
            update,
            bonus_texts,
            variation_choose_text=variation_choose_text,
        )
        keyboard = formatter.create_product_detail_keyboard(product_id, current_page, variations, update)
        
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
        product_choose_text, _ = _get_bot_selection_prompts(session)
        
        products = product_service.list_products(page=current_page, per_page=formatter.ITEMS_PER_PAGE, only_active=True)
        total_count = product_service.get_total_count(only_active=True)
        total_pages = formatter.calculate_total_pages(total_count)
        
        message = formatter.format_product_list(
            products,
            current_page,
            total_pages,
            update,
            product_choose_text=product_choose_text,
        )
        keyboard = formatter.create_product_keyboard(products, current_page, total_pages, update)
        
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
        
        # Get variation and actual stock
        variation = variation_service.get_variation_by_id(variation_id)
        if not variation:
            await query.edit_message_text("❌ Variation not found.")
            return
        
        product = product_service.get_product_by_id(variation.product_id)
        if not product:
            await query.edit_message_text("❌ Product not found.")
            return
        
        actual_stock = get_actual_stock(variation, product, variation_service)
        
        # Get applicable bonus
        from src.database.services.bonus_tier_service import BonusTierService
        bonus_service = BonusTierService(session)
        bonus_tier = bonus_service.get_applicable_bonus(variation_id, quantity, actual_stock)
        bonus_quantity = bonus_tier.bonus_quantity if bonus_tier else 0
        total_items = quantity + bonus_quantity
        
        # Validate stock including bonus
        if actual_stock < total_items:
            await query.edit_message_text(
                f"❌ Insufficient stock. Available: {actual_stock}, Requested: {total_items} (quantity: {quantity} + bonus: {bonus_quantity})"
            )
            return
        
        # Create order with bonus
        try:
            order = order_service.create_order(
                user_id=user_id,
                variation_id=variation_id,
                quantity=quantity,
                bonus_quantity=bonus_quantity,
            )
        except ValueError as e:
            await query.edit_message_text(f"❌ {str(e)}")
            return

        # Fire order-created notification (best effort, non-blocking for user flow)
        try:
            notify_service = OrderNotificationService(session, bot=context.bot)
            # Do not await strictly; but since we are already async, we await and ignore errors.
            await notify_service.send_order_created_async(order.id)
        except Exception as e:
            logger.warning(f"Order created notification failed for {order.id}: {e}")
        
        # Create payment URL
        try:
            import os
            import sys
            import time
            import json

            # Determine payment provider (default: payos)
            payment_provider = os.getenv("PAYMENT_PROVIDER_DEFAULT", "payos").lower()
            try:
                from config.config import PAYMENT_PROVIDER_DEFAULT as _PAYMENT_PROVIDER_DEFAULT

                if _PAYMENT_PROVIDER_DEFAULT:
                    payment_provider = str(_PAYMENT_PROVIDER_DEFAULT).lower()
            except ModuleNotFoundError:
                pass

            # PayOS flow (default)
            if payment_provider == "payos":
                try:
                    from config.config import (
                        PAYOS_BASE_URL,
                        PAYOS_PARTNER_CODE,
                        PAYOS_CLIENT_ID,
                        PAYOS_API_KEY,
                        PAYOS_CHECKSUM_KEY,
                        PAYOS_RETURN_URL,
                        PAYOS_CANCEL_URL,
                    )
                except ModuleNotFoundError:
                    PAYOS_BASE_URL = os.getenv("PAYOS_BASE_URL", "https://api-merchant.payos.vn")
                    PAYOS_PARTNER_CODE = os.getenv("PAYOS_PARTNER_CODE", "")
                    PAYOS_CLIENT_ID = os.getenv("PAYOS_CLIENT_ID", "")
                    PAYOS_API_KEY = os.getenv("PAYOS_API_KEY", "")
                    PAYOS_CHECKSUM_KEY = os.getenv("PAYOS_CHECKSUM_KEY", "")
                    PAYOS_RETURN_URL = os.getenv("PAYOS_RETURN_URL", os.getenv("REDIRECT_URL", "https://t.me/your_bot"))
                    PAYOS_CANCEL_URL = os.getenv("PAYOS_CANCEL_URL", os.getenv("REDIRECT_URL", "https://t.me/your_bot"))

                if not PAYOS_CLIENT_ID or not PAYOS_API_KEY or not PAYOS_CHECKSUM_KEY:
                    await query.answer("Payment configuration error", show_alert=True)
                    await query.edit_message_text(
                        "❌ Payment configuration error.\n\n"
                        "PAYOS_CLIENT_ID / PAYOS_API_KEY / PAYOS_CHECKSUM_KEY is not configured.\n"
                        "Please set environment variables or update config/config.py"
                    )
                    return

                try:
                    from src.payos.client import PayOSClient, PayOSCredentials
                    from src.bot.utils.qr import make_qr_png_bytes
                except Exception as e:
                    logger.error(f"Failed to import PayOS modules: {e}", exc_info=True)
                    await query.edit_message_text("❌ Payment module error. Please contact support.")
                    return

                # Assign PayOS identifiers on the order
                try:
                    payos_order_code = order_service.generate_payos_order_code()
                    order.payment_provider = "payos"
                    order.payos_order_code = payos_order_code
                    session.commit()
                except Exception as e:
                    logger.error(f"Failed to set PayOS orderCode: {e}", exc_info=True)
                    await query.edit_message_text("❌ Error preparing payment. Please try again.")
                    return

                payos = PayOSClient(
                    base_url=PAYOS_BASE_URL,
                    credentials=PayOSCredentials(
                        client_id=PAYOS_CLIENT_ID,
                        api_key=PAYOS_API_KEY,
                        checksum_key=PAYOS_CHECKSUM_KEY,
                        partner_code=PAYOS_PARTNER_CODE,
                    ),
                )

                # PayOS description can be restrictive; keep it short.
                order_prefix = os.getenv("ORDER_PREFIX", "MTK")
                description = f"{order_prefix}{order.id}"[:9]
                
                # Set PayOS payment link expiration to 30 minutes (same as Pay2S timeout)
                # PayOS will automatically expire the payment link after this time
                expired_at = int(time.time()) + 30 * 60
                logger.info(f"Creating PayOS payment link for order {order.id} with 30-minute expiration (expires at timestamp {expired_at})")

                try:
                    payos_resp = payos.create_payment_link(
                        order_code=int(payos_order_code),
                        amount=int(order.total_amount),
                        description=description,
                        return_url=PAYOS_RETURN_URL,
                        cancel_url=PAYOS_CANCEL_URL,
                        expired_at=expired_at,  # 30 minutes from now
                    )
                except Exception as e:
                    logger.error(f"PayOS create link failed: {e}", exc_info=True)
                    await query.edit_message_text("❌ Payment creation failed. Please try again later.")
                    return

                pay_data = (payos_resp or {}).get("data") or {}
                payment_link_id = pay_data.get("paymentLinkId")
                checkout_url = pay_data.get("checkoutUrl")
                qr_payload = pay_data.get("qrCode")

                # Persist PayOS fields for webhook reconciliation / cancellation
                try:
                    order.payos_payment_link_id = str(payment_link_id) if payment_link_id else None
                    order.payos_checkout_url = str(checkout_url) if checkout_url else None
                    session.commit()
                except Exception as e:
                    logger.warning(f"Failed to store PayOS payment link fields: {e}")

                state_manager.update_user_state(user_id, pending_order_id=order.id)

                # Format payment message with item details
                payment_message, caption = format_payment_message(order, update, session)

                cancel_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel_order_{order.id}")]
                ])

                # Keep original message ID so webhook can delete it too
                text_message_id = query.message.message_id

                # Edit the order confirmation message into payment message
                await query.edit_message_text(payment_message)

                if qr_payload:
                    try:
                        qr_image = make_qr_png_bytes(str(qr_payload))

                        sent_message = await context.bot.send_photo(
                            chat_id=user_id,
                            photo=qr_image,
                            caption=caption,
                            reply_markup=cancel_keyboard,
                        )

                        message_ids = [text_message_id, sent_message.message_id]
                        state_manager.update_user_state(
                            user_id,
                            payment_message_id=sent_message.message_id,
                            payment_message_ids=message_ids,
                        )
                        order.payment_message_ids = json.dumps(message_ids)
                        session.commit()
                    except Exception as e:
                        logger.error(f"Failed to send PayOS QR image: {e}", exc_info=True)
                        # Fallback: send payment message only (no URL)
                        fallback = payment_message
                        edited = await context.bot.send_message(
                            chat_id=user_id,
                            text=fallback,
                            reply_markup=cancel_keyboard,
                        )
                        message_ids = [text_message_id, edited.message_id]
                        state_manager.update_user_state(
                            user_id,
                            payment_message_id=edited.message_id,
                            payment_message_ids=message_ids,
                        )
                        order.payment_message_ids = json.dumps(message_ids)
                        session.commit()
                else:
                    # No QR payload - fallback to payment message only (no URL)
                    fallback = payment_message
                    edited = await context.bot.send_message(
                        chat_id=user_id,
                        text=fallback,
                        reply_markup=cancel_keyboard,
                    )
                    message_ids = [text_message_id, edited.message_id]
                    state_manager.update_user_state(
                        user_id,
                        payment_message_id=edited.message_id,
                        payment_message_ids=message_ids,
                    )
                    order.payment_message_ids = json.dumps(message_ids)
                    session.commit()

                return
            
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
            
            # Log and validate bank accounts format
            logger.info(f"Bank accounts type: {type(DEFAULT_BANK_ACCOUNTS)}, value: {DEFAULT_BANK_ACCOUNTS}")
            
            # Ensure bank accounts have correct format per Pay2S API spec
            validated_bank_accounts = []
            for bank in DEFAULT_BANK_ACCOUNTS:
                if isinstance(bank, dict) and "account_number" in bank and "bank_id" in bank:
                    validated_bank_accounts.append({
                        "account_number": str(bank["account_number"]),
                        "bank_id": str(bank["bank_id"]).upper()  # Ensure uppercase bank_id
                    })
                else:
                    logger.warning(f"Invalid bank account format: {bank}")
            
            if not validated_bank_accounts:
                error_msg = (
                    "❌ Payment configuration error.\n\n"
                    "Bank accounts have invalid format.\n"
                    f"Expected: [{{'account_number': '...', 'bank_id': '...'}}]\n"
                    f"Got: {DEFAULT_BANK_ACCOUNTS}\n"
                )
                await query.answer("Payment configuration error", show_alert=True)
                await query.edit_message_text(error_msg)
                logger.error(f"Invalid bank accounts format: {DEFAULT_BANK_ACCOUNTS}")
                return
            
            # Use validated bank accounts
            bank_accounts_to_use = validated_bank_accounts
            logger.info(f"Using validated bank accounts: {bank_accounts_to_use}")
            
            # Get IPN URL from environment or use default
            ipn_url = os.getenv("IPN_URL", f"http://localhost:{os.getenv('IPN_PORT', '5001')}/ipn")
            redirect_url = os.getenv("REDIRECT_URL", "https://t.me/your_bot")
            
            # Create order info (10-32 chars, alphanumeric ONLY - no special chars!)
            # API spec: "chỉ chấp nhận ký tự chữ + số, không dấu gạch ngang hoặc đặc biệt"
            # Format: MTK + order_id (no underscores or special characters!)
            order_prefix = os.getenv("ORDER_PREFIX", "MTK")
            order_info = f"{order_prefix}{order.id}"[:32]
            
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
                bank_accounts=bank_accounts_to_use,
                request_id=request_id,
            )
            
            logger.info(f"Payment response keys: {payment_response.keys()}")
            logger.info(f"Payment response resultCode type: {type(payment_response.get('resultCode'))}, value: {payment_response.get('resultCode')}")
            
            # Extract payment URL and QR code
            # Handle resultCode as both string "0" or integer 0
            result_code = payment_response.get("resultCode")
            is_success = (result_code == 0 or result_code == "0") and payment_response.get("payUrl")
            
            if is_success:
                payment_url = payment_response["payUrl"]
                logger.info(f"Payment created successfully! payUrl: {payment_url[:50]}...")
                
                # Update order with transaction ID if available
                transaction_id = payment_response.get("transId")
                logger.info(f"Transaction ID from response: {transaction_id}")
                
                if transaction_id:
                    order_service.update_order_status(
                        order.id,
                        order.status,  # Keep current status
                        payment_transaction_id=transaction_id,
                    )
                    logger.info(f"Updated order {order.id} with transaction_id: {transaction_id}")
                else:
                    logger.warning(f"No transId in payment response for order {order.id}")
                
                # Update user state
                state_manager.update_user_state(user_id, pending_order_id=order.id)
                
                # Format payment message with item details
                payment_message, caption_base = format_payment_message(order, update, session)
                
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
                    
                    # Get the original message ID before editing
                    text_message_id = query.message.message_id
                    
                    # Edit the callback message first
                    await query.edit_message_text(payment_message)
                    
                    # Add bank info to caption
                    bank_info = (
                        f"\n\n🏦 Bank Information:\n"
                        f"  • Bank: {qr_list[0].get('bank_name', 'N/A')}\n"
                        f"  • Account: {qr_list[0].get('account_number', 'N/A')}\n"
                        f"  • Name: {qr_list[0].get('account_name', 'N/A')}"
                    )
                    caption_with_bank = caption_base + bank_info
                    
                    # Send QR code as photo with cancel button
                    sent_message = await context.bot.send_photo(
                        chat_id=user_id,
                        photo=InputFile(qr_image, filename="qr_code.png"),
                        caption=caption_with_bank,
                        reply_markup=cancel_keyboard
                    )
                    
                    # Store both message IDs for later deletion (in state and database)
                    message_ids = [text_message_id, sent_message.message_id]
                    state_manager.update_user_state(
                        user_id, 
                        payment_message_id=sent_message.message_id,
                        payment_message_ids=message_ids
                    )
                    
                    # Also store in database for IPN server to access
                    import json
                    order.payment_message_ids = json.dumps(message_ids)
                    session.commit()
                    logger.info(f"Stored payment message IDs in database: {message_ids}")
                else:
                    # Fallback to text message with payment URL if QR code not available
                    bank_info = ""
                    if qr_list and len(qr_list) > 0:
                        bank_info = (
                            f"\n🏦 Bank Information:\n"
                            f"  • Bank: {qr_list[0].get('bank_id', 'N/A')}\n"
                            f"  • Account: {qr_list[0].get('account_number', 'N/A')}\n"
                            f"  • Name: {qr_list[0].get('account_name', 'N/A')}"
                        )
                    payment_message += f"{bank_info}\n\n🔗 Payment link:\n{payment_url}"
                    # Create cancel button for text message too
                    cancel_keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel_order_{order.id}")]
                    ])
                    
                    # Get the original message ID
                    text_message_id = query.message.message_id
                    edited_message = await query.edit_message_text(payment_message, reply_markup=cancel_keyboard)
                    
                    # Store message ID for later deletion (use edited message ID)
                    if edited_message:
                        message_ids = [text_message_id]
                        state_manager.update_user_state(
                            user_id, 
                            payment_message_id=edited_message.message_id,
                            payment_message_ids=message_ids
                        )
                        
                        # Also store in database for IPN server to access
                        import json
                        order.payment_message_ids = json.dumps(message_ids)
                        session.commit()
                        logger.info(f"Stored payment message IDs in database: {message_ids}")
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
        confirmation = t('commands.language.changed', update, lang_name=lang_display)
        await query.edit_message_text(confirmation)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error setting language: {str(e)}", exc_info=True)
        await query.answer("❌ Error changing language. Please try again.", show_alert=True)
    finally:
        session.close()

