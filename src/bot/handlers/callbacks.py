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
from src.database.services.bot_ui_settings_service import BotUiSettingsService
from src.bot.messages.product_formatter import ProductFormatter
from src.bot.messages.product_detail_formatter import ProductDetailFormatter
from src.bot.messages.order_confirmation_formatter import OrderConfirmationFormatter
from src.bot.states.state_manager import StateManager
from src.database.models.enums import DeliveryType, OrderStatus
from src.database.services.auto_cancel_service import PAYMENT_EXPIRE_MINUTES

logger = logging.getLogger(__name__)


# Global state manager instance
state_manager = StateManager()

# Sentinel returned for UPGRADE products to signal "stock doesn't apply".
# Renderers treat any value >= this threshold as unlimited so the customer
# isn't shown a meaningless inventory count.
UNLIMITED_STOCK_SENTINEL = 999_999


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
    if product.delivery_type == DeliveryType.UPGRADE:
        # UPGRADE products are not inventory-backed — only is_active gates ordering.
        return UNLIMITED_STOCK_SENTINEL
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
    auto_cancel = t('payment.auto_cancel_30min', update) if update else "⏰ This order will be automatically cancelled if payment is not completed within 10 minutes."
    auto_cancel_short = t('payment.auto_cancel_short', update) if update else "⏰ Auto-cancels in 10 minutes if unpaid"
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


async def handle_show_products_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle show_products_list callback — send the full product list as a new message."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    state_manager.update_user_state(user_id, current_page=1)

    session_factory = get_session_factory()
    session = session_factory()

    try:
        product_service = ProductService(session)
        formatter = ProductFormatter()
        product_choose_text, _ = _get_bot_selection_prompts(session)

        products = product_service.list_products(page=1, per_page=9999, only_active=True)
        message = formatter.format_product_list(product_choose_text=product_choose_text)
        keyboard = formatter.create_product_keyboard(products, update)

        await query.edit_message_text(message, reply_markup=keyboard)
    finally:
        session.close()


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

        products = product_service.list_products(page=1, per_page=9999, only_active=True)
        message = formatter.format_product_list(product_choose_text=product_choose_text)
        keyboard = formatter.create_product_keyboard(products, update)

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

        sold_count = variation_service.get_sold_count_by_product(product_id)

        # Format message and keyboard
        message = formatter.format_product_detail(
            product,
            variations,
            total_stock,
            update,
            bonus_texts,
            variation_choose_text=variation_choose_text,
            sold_count=sold_count,
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

        # Show out-of-stock screen instead of quantity form
        if actual_stock == 0:
            msg = t('products.order_confirmation.variation_out_of_stock', update)
            msg = msg.format(variation_name=variation.name)
            back_text = t('products.order_confirmation.back_to_product', update)
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(back_text, callback_data=f"product_{product.id}")]
            ])
            await query.edit_message_text(msg, reply_markup=keyboard, parse_mode="HTML")
            return

        # Update user state
        state_manager.update_user_state(
            user_id,
            selected_variation_id=variation_id,
            quantity=1,  # Default quantity
        )
        
        # Format order confirmation with bonus and/or discount
        quantity = 1
        from src.bot.utils.language import get_user_language
        language = get_user_language(update)
        benefit_mode = getattr(variation, 'benefit_mode', 'bonus')
        bonus_quantity, bonus_label = formatter.get_applicable_bonus(
            variation_id, quantity, actual_stock, session, language
        )
        discount_label, discount_amount = formatter.get_applicable_discount(
            variation_id, quantity, variation.price, session, language, benefit_mode
        )
        sold_count = variation_service.get_sold_count_by_variation(variation_id)
        message = formatter.format_order_confirmation(
            product, variation, quantity, update, bonus_quantity, bonus_label,
            discount_label=discount_label, discount_amount=discount_amount,
            sold_count=sold_count,
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
        
        # Format updated order confirmation with bonus and/or discount
        from src.bot.utils.language import get_user_language
        language = get_user_language(update)
        benefit_mode = getattr(variation, 'benefit_mode', 'bonus')
        bonus_quantity, bonus_label = formatter.get_applicable_bonus(
            variation_id, new_quantity, actual_stock, session, language
        )
        discount_label, discount_amount = formatter.get_applicable_discount(
            variation_id, new_quantity, variation.price, session, language, benefit_mode
        )
        sold_count = variation_service.get_sold_count_by_variation(variation_id)
        message = formatter.format_order_confirmation(
            product, variation, new_quantity, update, bonus_quantity, bonus_label,
            discount_label=discount_label, discount_amount=discount_amount,
            sold_count=sold_count,
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
        # Mutually exclusive: clear topup-amount mode if active
        order_message_id = query.message.message_id
        user_state.awaiting_topup_amount = False
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
        
        # Update the order confirmation message with bonus and/or discount
        if user_state.order_message_id:
            from src.bot.utils.language import get_user_language
            language = get_user_language(update)
            benefit_mode = getattr(variation, 'benefit_mode', 'bonus')
            bonus_quantity, bonus_label = formatter.get_applicable_bonus(
                user_state.selected_variation_id, quantity, actual_stock, session, language
            )
            discount_label, discount_amount = formatter.get_applicable_discount(
                user_state.selected_variation_id, quantity, variation.price, session, language, benefit_mode
            )
            sold_count = variation_service.get_sold_count_by_variation(user_state.selected_variation_id)
            message = formatter.format_order_confirmation(
                product, variation, quantity, update, bonus_quantity, bonus_label,
                discount_label=discount_label, discount_amount=discount_amount,
                sold_count=sold_count,
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

        sold_count = variation_service.get_sold_count_by_product(product_id)

        # Format message and keyboard
        message = formatter.format_product_detail(
            product,
            variations,
            total_stock,
            update,
            bonus_texts,
            variation_choose_text=variation_choose_text,
            sold_count=sold_count,
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

        products = product_service.list_products(page=1, per_page=9999, only_active=True)
        message = formatter.format_product_list(product_choose_text=product_choose_text)
        keyboard = formatter.create_product_keyboard(products, update)

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
        
        # Determine which benefits apply for this variation
        benefit_mode = getattr(variation, 'benefit_mode', 'bonus')

        # Get applicable bonus (if mode includes bonus)
        from src.database.services.bonus_tier_service import BonusTierService
        bonus_service = BonusTierService(session)
        bonus_tier = None
        bonus_quantity = 0
        if benefit_mode in ('bonus', 'both'):
            bonus_tier = bonus_service.get_applicable_bonus(variation_id, quantity, actual_stock)
            bonus_quantity = bonus_tier.bonus_quantity if bonus_tier else 0

        total_items = quantity + bonus_quantity

        # Validate stock including bonus
        if actual_stock < total_items:
            await query.edit_message_text(
                f"❌ Insufficient stock. Available: {actual_stock}, Requested: {total_items} (quantity: {quantity} + bonus: {bonus_quantity})"
            )
            return

        # Get applicable discount (if mode includes discount)
        from src.database.services.discount_tier_service import DiscountTierService
        discount_service = DiscountTierService(session)
        discount_tier = None
        if benefit_mode in ('discount', 'both'):
            discount_tier = discount_service.get_applicable_discount(variation_id, quantity)

        # Create order with bonus and/or discount
        try:
            order = order_service.create_order(
                user_id=user_id,
                variation_id=variation_id,
                quantity=quantity,
                bonus_quantity=bonus_quantity,
                discount_tier=discount_tier,
            )
        except ValueError as e:
            await query.edit_message_text(f"❌ {str(e)}")
            return

        # NEW_ORDER_CREATED notification is disabled; only ORDER_PAID is sent after delivery.

        # --- Show payment method picker (balance vs QR) ---
        from src.database.services.balance_service import BalanceService
        from src.database.services.bot_user_service import BotUserService
        from src.bot.utils.language import t as _t

        bot_user_svc = BotUserService(session)
        bot_user = bot_user_svc.get_user_by_telegram_id(user_id)
        if bot_user:
            balance_svc = BalanceService(session)
            current_balance = balance_svc.get_balance(bot_user.id)
        else:
            current_balance = 0

        picker_text = (
            f"{_t('balance.pay_method_title', update)}\n\n"
            f"{_t('balance.pay_method_balance_line', update, balance=f'{current_balance:,}')}\n"
            f"{_t('balance.pay_method_total_line', update, total=f'{order.total_amount:,}')}"
        )
        picker_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    _t("balance.pay_with_balance_button", update),
                    callback_data=f"pay_balance_{order.id}",
                ),
                InlineKeyboardButton(
                    _t("balance.pay_with_qr_button", update),
                    callback_data=f"pay_qr_{order.id}",
                ),
            ]
        ])
        state_manager.update_user_state(
            user_id,
            pending_order_id=order.id,
            pending_payment_order_id=order.id,
        )
        await query.edit_message_text(picker_text, reply_markup=picker_keyboard)

    finally:
        session.close()


async def _create_qr_for_order(
    order_id: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    reply_to_query=None,
) -> None:
    """
    Create a PayOS or Pay2S QR payment for an existing order and send it to the user.

    Args:
        order_id: The Order.id to pay.
        update: Telegram update for language and user_id.
        context: Bot context for sending messages.
        reply_to_query: If set (a CallbackQuery), we will edit it for the text message.
    """
    import os
    import time
    import json

    user_id = update.effective_user.id

    session_factory = get_session_factory()
    session = session_factory()
    try:
        order_service = OrderService(session)
        order = order_service.get_order_by_id(order_id)
        if not order:
            msg = "❌ Order not found."
            if reply_to_query:
                await reply_to_query.edit_message_text(msg)
            else:
                await context.bot.send_message(chat_id=user_id, text=msg)
            return

        if order.user_id != user_id:
            msg = "❌ Access denied."
            if reply_to_query:
                await reply_to_query.edit_message_text(msg)
            return

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
                err = (
                    "❌ Payment configuration error.\n\n"
                    "PAYOS_CLIENT_ID / PAYOS_API_KEY / PAYOS_CHECKSUM_KEY is not configured.\n"
                    "Please set environment variables or update config/config.py"
                )
                if reply_to_query:
                    await reply_to_query.edit_message_text(err)
                else:
                    await context.bot.send_message(chat_id=user_id, text=err)
                return

            try:
                from src.payos.client import PayOSClient, PayOSCredentials
                from src.bot.utils.qr import make_qr_png_bytes
            except Exception as e:
                logger.error(f"Failed to import PayOS modules: {e}", exc_info=True)
                err = "❌ Payment module error. Please contact support."
                if reply_to_query:
                    await reply_to_query.edit_message_text(err)
                else:
                    await context.bot.send_message(chat_id=user_id, text=err)
                return

            # If a complete payment link already exists for this order, reuse it
            # without calling the PayOS API again. This prevents duplicate payment
            # links when the user double-taps the QR button.
            if order.payos_order_code and order.payos_checkout_url:
                payos_order_code = order.payos_order_code
                qr_payload = order.payos_qr_code or order.payos_checkout_url
                logger.info(f"Reusing existing PayOS link for order {order.id} (code={payos_order_code})")
            else:
                # Assign PayOS identifiers — reuse existing code if one was already
                # committed to avoid orphaning it on a concurrent double-tap.
                try:
                    if order.payos_order_code:
                        payos_order_code = order.payos_order_code
                    else:
                        payos_order_code = order_service.generate_payos_order_code()
                        order.payment_provider = "payos"
                        order.payos_order_code = payos_order_code
                        session.commit()
                except Exception as e:
                    logger.error(f"Failed to set PayOS orderCode: {e}", exc_info=True)
                    err = "❌ Error preparing payment. Please try again."
                    if reply_to_query:
                        await reply_to_query.edit_message_text(err)
                    else:
                        await context.bot.send_message(chat_id=user_id, text=err)
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

                order_prefix = os.getenv("ORDER_PREFIX", "MTK")
                description = f"{order_prefix}{order.id}"[:9]
                expired_at = int(time.time()) + PAYMENT_EXPIRE_MINUTES * 60
                logger.info(f"Creating PayOS payment link for order {order.id} with {PAYMENT_EXPIRE_MINUTES}-min expiration")

                try:
                    payos_resp = payos.create_payment_link(
                        order_code=int(payos_order_code),
                        amount=int(order.total_amount),
                        description=description,
                        return_url=PAYOS_RETURN_URL,
                        cancel_url=PAYOS_CANCEL_URL,
                        expired_at=expired_at,
                    )
                except Exception as e:
                    logger.error(f"PayOS create link failed: {e}", exc_info=True)
                    err = "❌ Payment creation failed. Please try again later."
                    if reply_to_query:
                        await reply_to_query.edit_message_text(err)
                    else:
                        await context.bot.send_message(chat_id=user_id, text=err)
                    return

                pay_data = (payos_resp or {}).get("data") or {}
                payment_link_id = pay_data.get("paymentLinkId")
                checkout_url = pay_data.get("checkoutUrl")
                qr_code = pay_data.get("qrCode")
                qr_payload = qr_code or checkout_url

                try:
                    order.payos_payment_link_id = str(payment_link_id) if payment_link_id else None
                    order.payos_checkout_url = str(checkout_url) if checkout_url else None
                    order.payos_qr_code = str(qr_code) if qr_code else None
                    session.commit()
                except Exception as e:
                    logger.warning(f"Failed to store PayOS payment link fields: {e}")

            state_manager.update_user_state(user_id, pending_order_id=order.id)

            payment_message, caption = format_payment_message(order, update, session)

            cancel_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel_order_{order.id}")]
            ])

            # Edit the picker/confirmation message into the text payment message
            if reply_to_query:
                from telegram.error import BadRequest as TgBadRequest
                try:
                    await reply_to_query.edit_message_text(payment_message)
                except TgBadRequest as exc:
                    if "is not modified" not in str(exc):
                        raise
                text_message_id = reply_to_query.message.message_id
            else:
                sent_text = await context.bot.send_message(chat_id=user_id, text=payment_message)
                text_message_id = sent_text.message_id

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
                    fallback = await context.bot.send_message(
                        chat_id=user_id, text=payment_message, reply_markup=cancel_keyboard,
                    )
                    message_ids = [text_message_id, fallback.message_id]
                    state_manager.update_user_state(
                        user_id,
                        payment_message_id=fallback.message_id,
                        payment_message_ids=message_ids,
                    )
                    order.payment_message_ids = json.dumps(message_ids)
                    session.commit()
            else:
                fallback = await context.bot.send_message(
                    chat_id=user_id, text=payment_message, reply_markup=cancel_keyboard,
                )
                message_ids = [text_message_id, fallback.message_id]
                state_manager.update_user_state(
                    user_id,
                    payment_message_id=fallback.message_id,
                    payment_message_ids=message_ids,
                )
                order.payment_message_ids = json.dumps(message_ids)
                session.commit()
            return

        # ---- Pay2S fallback ----
        try:
            from config.config import (
                PAY2S_ENDPOINT,
                PARTNER_CODE,
                ACCESS_KEY,
                SECRET_KEY,
                DEFAULT_BANK_ACCOUNTS,
            )
        except ModuleNotFoundError:
            PAY2S_ENDPOINT = os.getenv("PAY2S_ENDPOINT", "...")
            PARTNER_CODE = os.getenv("PAY2S_PARTNER_CODE", "...")
            ACCESS_KEY = os.getenv("PAY2S_ACCESS_KEY", "...")
            SECRET_KEY = os.getenv("PAY2S_SECRET_KEY", "...")
            DEFAULT_BANK_ACCOUNTS = os.getenv("DEFAULT_BANK_ACCOUNTS", "[]")
            if isinstance(DEFAULT_BANK_ACCOUNTS, str):
                try:
                    DEFAULT_BANK_ACCOUNTS = json.loads(DEFAULT_BANK_ACCOUNTS)
                except Exception:
                    DEFAULT_BANK_ACCOUNTS = []

        from src.pay2s import create_payment

        if not PAY2S_ENDPOINT or PAY2S_ENDPOINT == '...' or not PAY2S_ENDPOINT.startswith(('http://', 'https://')):
            error_msg = (
                "❌ Payment configuration error.\n\n"
                "The Pay2S endpoint is not configured correctly.\n"
                "Please set PAY2S_ENDPOINT environment variable or update config/config.py\n\n"
                f"Current value: {repr(PAY2S_ENDPOINT)}"
            )
            if reply_to_query:
                await reply_to_query.edit_message_text(error_msg)
            else:
                await context.bot.send_message(chat_id=user_id, text=error_msg)
            logger.error(f"Invalid PAY2S_ENDPOINT: {repr(PAY2S_ENDPOINT)}")
            return

        if not ACCESS_KEY or ACCESS_KEY == '...' or not SECRET_KEY or SECRET_KEY == '...':
            error_msg = (
                "❌ Payment configuration error.\n\n"
                "ACCESS_KEY or SECRET_KEY is not configured correctly.\n"
                "Please update config/config.py\n"
            )
            if reply_to_query:
                await reply_to_query.edit_message_text(error_msg)
            else:
                await context.bot.send_message(chat_id=user_id, text=error_msg)
            logger.error("Invalid ACCESS_KEY or SECRET_KEY in payment config")
            return

        if not DEFAULT_BANK_ACCOUNTS or len(DEFAULT_BANK_ACCOUNTS) == 0:
            error_msg = (
                "❌ Payment configuration error.\n\n"
                "No bank accounts configured.\n"
                "Please configure DEFAULT_BANK_ACCOUNTS in config/config.py\n"
            )
            if reply_to_query:
                await reply_to_query.edit_message_text(error_msg)
            else:
                await context.bot.send_message(chat_id=user_id, text=error_msg)
            logger.error("DEFAULT_BANK_ACCOUNTS not configured")
            return

        logger.info(f"Bank accounts type: {type(DEFAULT_BANK_ACCOUNTS)}, value: {DEFAULT_BANK_ACCOUNTS}")

        validated_bank_accounts = []
        for bank in DEFAULT_BANK_ACCOUNTS:
            if isinstance(bank, dict) and "account_number" in bank and "bank_id" in bank:
                validated_bank_accounts.append({
                    "account_number": str(bank["account_number"]),
                    "bank_id": str(bank["bank_id"]).upper()
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
            if reply_to_query:
                await reply_to_query.edit_message_text(error_msg)
            else:
                await context.bot.send_message(chat_id=user_id, text=error_msg)
            logger.error(f"Invalid bank accounts format: {DEFAULT_BANK_ACCOUNTS}")
            return

        bank_accounts_to_use = validated_bank_accounts
        logger.info(f"Using validated bank accounts: {bank_accounts_to_use}")

        ipn_url = os.getenv("IPN_URL", f"http://localhost:{os.getenv('IPN_PORT', '5001')}/ipn")
        redirect_url = os.getenv("REDIRECT_URL", "https://t.me/your_bot")

        order_prefix = os.getenv("ORDER_PREFIX", "MTK")
        order_info = f"{order_prefix}{order.id}"[:32]

        request_id = str(int(time.time() * 1000))

        logger.info(f"Creating payment: endpoint={PAY2S_ENDPOINT}, order_id={order.id}, amount={order.total_amount}, order_info={order_info}, request_id={request_id}")
        logger.debug(f"Bank accounts: {DEFAULT_BANK_ACCOUNTS}")
        logger.debug(f"IPN URL: {ipn_url}, Redirect URL: {redirect_url}")

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

        result_code = payment_response.get("resultCode")
        is_success = (result_code == 0 or result_code == "0") and payment_response.get("payUrl")

        if is_success:
            payment_url = payment_response["payUrl"]
            logger.info(f"Payment created successfully! payUrl: {payment_url[:50]}...")

            transaction_id = payment_response.get("transId")
            logger.info(f"Transaction ID from response: {transaction_id}")

            if transaction_id:
                order_service.update_order_status(
                    order.id,
                    order.status,
                    payment_transaction_id=transaction_id,
                )
                logger.info(f"Updated order {order.id} with transaction_id: {transaction_id}")
            else:
                logger.warning(f"No transId in payment response for order {order.id}")

            state_manager.update_user_state(user_id, pending_order_id=order.id)

            payment_message, caption_base = format_payment_message(order, update, session)

            qr_code_data = None
            qr_list = payment_response.get("qrList", [])
            if qr_list and len(qr_list) > 0:
                qr_code = qr_list[0].get("qrCode")
                if qr_code and qr_code.startswith("data:image/png;base64,"):
                    base64_data = qr_code.replace("data:image/png;base64,", "")
                    try:
                        qr_code_data = base64.b64decode(base64_data)
                    except Exception as e:
                        logger.warning(f"Failed to decode QR code: {str(e)}")
                        qr_code_data = None

            if qr_code_data:
                qr_image = BytesIO(qr_code_data)
                qr_image.name = "qr_code.png"

                cancel_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel_order_{order.id}")]
                ])

                if reply_to_query:
                    await reply_to_query.edit_message_text(payment_message)
                    text_message_id = reply_to_query.message.message_id
                else:
                    sent_text = await context.bot.send_message(chat_id=user_id, text=payment_message)
                    text_message_id = sent_text.message_id

                bank_info = (
                    f"\n\n🏦 Bank Information:\n"
                    f"  • Bank: {qr_list[0].get('bank_name', 'N/A')}\n"
                    f"  • Account: {qr_list[0].get('account_number', 'N/A')}\n"
                    f"  • Name: {qr_list[0].get('account_name', 'N/A')}"
                )
                caption_with_bank = caption_base + bank_info

                sent_message = await context.bot.send_photo(
                    chat_id=user_id,
                    photo=InputFile(qr_image, filename="qr_code.png"),
                    caption=caption_with_bank,
                    reply_markup=cancel_keyboard
                )

                message_ids = [text_message_id, sent_message.message_id]
                state_manager.update_user_state(
                    user_id,
                    payment_message_id=sent_message.message_id,
                    payment_message_ids=message_ids
                )

                order.payment_message_ids = json.dumps(message_ids)
                session.commit()
                logger.info(f"Stored payment message IDs in database: {message_ids}")
            else:
                bank_info = ""
                if qr_list and len(qr_list) > 0:
                    bank_info = (
                        f"\n🏦 Bank Information:\n"
                        f"  • Bank: {qr_list[0].get('bank_id', 'N/A')}\n"
                        f"  • Account: {qr_list[0].get('account_number', 'N/A')}\n"
                        f"  • Name: {qr_list[0].get('account_name', 'N/A')}"
                    )
                payment_message += f"{bank_info}\n\n🔗 Payment link:\n{payment_url}"
                cancel_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel_order_{order.id}")]
                ])

                if reply_to_query:
                    text_message_id = reply_to_query.message.message_id
                    edited_message = await reply_to_query.edit_message_text(payment_message, reply_markup=cancel_keyboard)
                else:
                    edited_message = await context.bot.send_message(
                        chat_id=user_id, text=payment_message, reply_markup=cancel_keyboard,
                    )
                    text_message_id = edited_message.message_id

                if edited_message:
                    message_ids = [text_message_id]
                    state_manager.update_user_state(
                        user_id,
                        payment_message_id=edited_message.message_id,
                        payment_message_ids=message_ids
                    )
                    order.payment_message_ids = json.dumps(message_ids)
                    session.commit()
                    logger.info(f"Stored payment message IDs in database: {message_ids}")
        else:
            error_msg = payment_response.get("message", "Unknown error")
            err_text = f"❌ Payment creation failed: {error_msg}"
            if reply_to_query:
                await reply_to_query.edit_message_text(err_text)
            else:
                await context.bot.send_message(chat_id=user_id, text=err_text)
            logger.error(f"Payment creation failed: {payment_response}")

    except ValueError as e:
        error_msg = str(e)
        logger.error(f"Payment configuration error: {error_msg}")
        err_text = f"❌ Configuration error: {error_msg}"
        if reply_to_query:
            await reply_to_query.edit_message_text(err_text)
        else:
            await context.bot.send_message(chat_id=user_id, text=err_text)
    except Exception as e:
        logger.error(f"Error creating payment: {str(e)}", exc_info=True)
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
        if reply_to_query:
            await reply_to_query.edit_message_text(error_message)
        else:
            await context.bot.send_message(chat_id=user_id, text=error_message)
    finally:
        session.close()


async def handle_pay_with_qr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Callback: pay_qr_{order_id} — user chose to pay via QR transfer.
    Delegates to _create_qr_for_order.
    """
    query = update.callback_query
    await query.answer()
    order_id = query.data.replace("pay_qr_", "")
    await _create_qr_for_order(order_id, update, context, reply_to_query=query)


async def handle_pay_with_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Callback: pay_balance_{order_id} — user chose to pay using wallet balance.
    Calls BalanceService.pay_order_with_balance atomically, then triggers
    fulfillment via IPNOrderProcessor.process_balance_paid_order.
    """
    import asyncio as _asyncio

    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    order_id = query.data.replace("pay_balance_", "")

    from src.bot.utils.language import t as _t
    from src.database.services.balance_service import BalanceService
    from src.database.services.bot_user_service import BotUserService

    session_factory = get_session_factory()
    session = session_factory()
    try:
        bot_user_svc = BotUserService(session)
        bot_user = bot_user_svc.get_user_by_telegram_id(user_id)
        if not bot_user:
            await query.edit_message_text("❌ User not found.")
            return

        balance_svc = BalanceService(session)

        # Load order to get total
        order_svc = OrderService(session)
        order = order_svc.get_order_by_id(order_id)
        if not order:
            await query.edit_message_text(_t("order.not_found", update))
            return

        order_total = order.total_amount  # capture before session closes
        success, reason = balance_svc.pay_order_with_balance(order_id, bot_user)
    finally:
        session.close()

    if success:
        await query.edit_message_text(_t("balance.balance_paid_success", update))

        # Trigger order fulfillment asynchronously
        try:
            from src.ipn import get_ipn_processor
            processor = get_ipn_processor()
            if processor:
                loop = _asyncio.get_running_loop()
                await loop.run_in_executor(
                    None,
                    lambda: processor.process_balance_paid_order(
                        order_id=order_id, request_loop=loop
                    ),
                )
            else:
                logger.warning(f"IPN processor not available for balance-paid order {order_id}")
        except Exception as exc:
            logger.error(f"Error in fulfillment for balance-paid order {order_id}: {exc}", exc_info=True)

        # Clear payment-related state
        state = state_manager.get_user_state(user_id)
        if state:
            state.pending_payment_order_id = None
            state.pending_order_id = None
            state_manager.set_user_state(user_id, state)

    elif reason == "insufficient":
        # Reload balance for display
        session2 = get_session_factory()()
        try:
            from src.database.services.balance_service import BalanceService as _BS
            from src.database.services.bot_user_service import BotUserService as _BUS
            _bot_user = _BUS(session2).get_user_by_telegram_id(user_id)
            bal = _BS(session2).get_balance(_bot_user.id) if _bot_user else 0
        finally:
            session2.close()

        insuf_text = _t(
            "balance.insufficient_balance",
            update,
            balance=f"{bal:,}",
            total=f"{order_total:,}",
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(_t("balance.topup_more_button", update), callback_data="topup_start"),
                InlineKeyboardButton(_t("balance.pay_with_qr_button", update), callback_data=f"pay_qr_{order_id}"),
            ]
        ])
        await query.edit_message_text(insuf_text, reply_markup=keyboard)

    elif reason == "already_processed":
        await query.edit_message_text(_t("balance.already_processed", update))

    else:
        await query.edit_message_text(_t("errors.generic", update))


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


_ORDERS_PER_PAGE = 8

_STATUS_EMOJI = {
    "pending": "⏳",
    "paid": "✅",
    "processing": "🔄",
    "delivered": "📦",
    "cancelled": "❌",
}


def _build_order_history_message_and_keyboard(orders, page, update):
    """Return (message_text, InlineKeyboardMarkup) for the order history list view."""
    from src.bot.utils.language import t

    total = len(orders)
    total_pages = max(1, (total + _ORDERS_PER_PAGE - 1) // _ORDERS_PER_PAGE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * _ORDERS_PER_PAGE
    page_orders = orders[start: start + _ORDERS_PER_PAGE]

    title = t("order_history.title", update)
    if total == 0:
        body = t("order_history.empty", update)
    else:
        body = t("order_history.count", update, count=total)
        if total_pages > 1:
            body += f"\n{t('order_history.page', update, current=page, total=total_pages)}"

    message = f"{title}\n\n{body}"

    keyboard = []
    for order in page_orders:
        status_val = order.status.value if hasattr(order.status, "value") else str(order.status)
        emoji = _STATUS_EMOJI.get(status_val, "❓")
        label = f"#{order.id} | {emoji} | {order.total_amount:,}đ"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"order_detail_{order.id}_from_{page}")])

    nav_row = []
    if page > 1:
        prev_text = t("buttons.prev", update)
        nav_row.append(InlineKeyboardButton(prev_text, callback_data=f"order_history_page_{page - 1}"))
    if page < total_pages:
        next_text = t("buttons.next", update)
        nav_row.append(InlineKeyboardButton(next_text, callback_data=f"order_history_page_{page + 1}"))
    if nav_row:
        keyboard.append(nav_row)

    return message, InlineKeyboardMarkup(keyboard)


async def handle_order_history_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle order_history and order_history_page_<N> callbacks."""
    from src.bot.utils.language import t

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data  # "order_history" or "order_history_page_<N>"

    page = 1
    if data.startswith("order_history_page_"):
        try:
            page = int(data.replace("order_history_page_", ""))
        except ValueError:
            page = 1

    session_factory = get_session_factory()
    session = session_factory()

    try:
        order_service = OrderService(session)
        orders = order_service.get_user_orders(user_id, status=OrderStatus.DELIVERED, limit=200)
        message, reply_markup = _build_order_history_message_and_keyboard(orders, page, update)
        await query.edit_message_text(message, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in handle_order_history_page: {str(e)}", exc_info=True)
        await query.answer(t("order_history.error", update), show_alert=True)
    finally:
        session.close()


async def handle_order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle order_detail_<order_id>_from_<page> callbacks."""
    import html
    from src.bot.utils.language import t

    query = update.callback_query
    await query.answer()

    data = query.data  # "order_detail_<order_id>_from_<page>"
    # Parse: strip prefix, then split on "_from_" to get order_id and source page
    raw = data.replace("order_detail_", "", 1)
    if "_from_" in raw:
        order_id, from_page_str = raw.rsplit("_from_", 1)
        try:
            from_page = int(from_page_str)
        except ValueError:
            from_page = 1
    else:
        order_id = raw
        from_page = 1

    session_factory = get_session_factory()
    session = session_factory()

    try:
        order_service = OrderService(session)
        details = order_service.get_order_with_details(order_id)

        if not details:
            await query.answer(t("order.not_found", update), show_alert=True)
            return

        status_val = details["status"]
        status_key = f"order_history.status_{status_val}"
        status_label = t(status_key, update)

        from datetime import datetime
        try:
            dt = datetime.fromisoformat(details["created_at"])
            date_str = dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            date_str = details["created_at"]

        lines = [
            t("order_history.detail_title", update),
            "",
            t("order_history.order_id", update, order_id=html.escape(str(details["id"]))),
            t("order_history.date", update, date=html.escape(str(date_str))),
            t("order_history.status", update, status=html.escape(str(status_label))),
            "",
            t("order_history.items_header", update),
        ]

        for item in details.get("items", []):
            product_name = item["product"]["name"] if item.get("product") else "?"
            variation_name = item["variation"]["name"] if item.get("variation") else "?"
            qty = item["quantity"]
            subtotal = item["subtotal"]
            lines.append(t(
                "order_history.item_line",
                update,
                product=html.escape(str(product_name)),
                variation=html.escape(str(variation_name)),
                qty=qty,
                subtotal=f"{subtotal:,}đ",
            ))
            if item.get("bonus_quantity"):
                lines.append(t("order_history.item_bonus", update, bonus=item["bonus_quantity"]))

            delivered_products = item.get("delivered_products") or []
            if delivered_products:
                lines.append(t("order_history.delivered_header", update))
                for delivered in delivered_products:
                    display_text = delivered.get("display") or ""
                    if not display_text:
                        continue
                    escaped = html.escape(str(display_text))
                    lines.append(t(
                        "order_history.delivered_line",
                        update,
                        data=f"<code>{escaped}</code>",
                    ))

        lines.append("")
        total = details["total_amount"]
        discount = details.get("discount_amount", 0)
        paid = total - discount

        if discount > 0:
            lines.append(t("order_history.total", update, total=f"{total:,}đ"))
            lines.append(t("order_history.discount", update, discount=f"{discount:,}đ"))
            lines.append(t("order_history.paid_amount", update, amount=f"{paid:,}đ"))
        else:
            lines.append(t("order_history.total", update, total=f"{total:,}đ"))

        txn_id = details.get("payment_transaction_id")
        if txn_id:
            lines.append(t("order_history.transaction", update, txn_id=html.escape(str(txn_id))))

        message = "\n".join(lines)

        back_text = t("order_history.back_to_list", update)
        keyboard = [[InlineKeyboardButton(back_text, callback_data=f"back_to_order_history_{from_page}")]]
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Error in handle_order_detail: {str(e)}", exc_info=True)
        await query.answer(t("order_history.error", update), show_alert=True)
    finally:
        session.close()


async def handle_back_to_order_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle back_to_order_history and back_to_order_history_<N> callbacks."""
    from src.bot.utils.language import t

    query = update.callback_query
    await query.answer()

    data = query.data
    page = 1
    if data.startswith("back_to_order_history_"):
        try:
            page = int(data.replace("back_to_order_history_", ""))
        except ValueError:
            page = 1

    user_id = query.from_user.id

    session_factory = get_session_factory()
    session = session_factory()

    try:
        order_service = OrderService(session)
        orders = order_service.get_user_orders(user_id, status=OrderStatus.DELIVERED, limit=200)
        message, reply_markup = _build_order_history_message_and_keyboard(orders, page, update)
        await query.edit_message_text(message, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in handle_back_to_order_history: {str(e)}", exc_info=True)
        await query.answer(t("order_history.error", update), show_alert=True)
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

