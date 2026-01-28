"""
Command handlers for the Telegram bot.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.database.connection import get_session_factory
from src.database.services.product_service import ProductService
from src.database.services.bot_user_service import BotUserService
from src.database.services.user_preference_service import UserPreferenceService
from src.bot.messages.product_formatter import ProductFormatter
from src.bot.states.state_manager import StateManager
from src.bot.utils.language import get_user_language, t
from src.bot.utils.keyboard import get_persistent_keyboard


# Global state manager instance
state_manager = StateManager()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    user = update.effective_user
    
    # Track user in database
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        bot_user_service = BotUserService(session)
        bot_user_service.track_user(
            telegram_user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )
    except Exception as e:
        # Log error but don't fail the command
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error tracking user: {str(e)}", exc_info=True)
    finally:
        session.close()
    
    # Get user language
    language = get_user_language(update)
    
    welcome_message = (
        f"{t('commands.start.welcome', update, name=user.first_name or 'User')}\n\n"
        f"{t('commands.start.description', update)}\n"
        f"{t('commands.start.help_hint', update)}"
    )
    # Show persistent keyboard with Products button
    keyboard = get_persistent_keyboard(update)
    await update.message.reply_text(welcome_message, reply_markup=keyboard)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /help command.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    user = update.effective_user
    
    # Track user in database (if not already tracked)
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        bot_user_service = BotUserService(session)
        bot_user_service.track_user(
            telegram_user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )
    except Exception as e:
        # Log error but don't fail the command
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error tracking user: {str(e)}", exc_info=True)
    finally:
        session.close()
    
    from src.bot.utils.admin_check import is_admin
    
    user_id = user.id
    is_user_admin = is_admin(user_id)
    
    help_message = (
        f"{t('commands.help.title', update)}\n\n"
        f"{t('commands.help.start', update)}\n"
        f"{t('commands.help.help', update)}\n"
        f"{t('commands.help.products', update)}\n\n"
        f"{t('commands.help.interaction_hint', update)}"
    )
    
    if is_user_admin:
        help_message += (
            f"\n\n{t('commands.help.admin_title', update)}\n"
            f"{t('commands.help.notify_all', update)}\n"
            f"{t('commands.help.notify_user', update)}\n"
            f"{t('commands.help.notify_active', update)}"
        )
    
    # Show persistent keyboard
    keyboard = get_persistent_keyboard(update)
    await update.message.reply_text(help_message, reply_markup=keyboard)


async def products_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /products command - show product list.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    user = update.effective_user
    user_id = user.id
    
    # Track user in database (if not already tracked)
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        bot_user_service = BotUserService(session)
        bot_user_service.track_user(
            telegram_user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )
        
        # Initialize user state if needed
        user_state = state_manager.get_user_state(user_id)
        if not user_state:
            state_manager.update_user_state(user_id, current_page=1)
            current_page = 1
        else:
            current_page = user_state.current_page
        
        # Get products
        product_service = ProductService(session)
        formatter = ProductFormatter()
        
        # Get products for the page
        products = product_service.list_products(
            page=current_page,
            per_page=formatter.ITEMS_PER_PAGE,
            only_active=True,
        )
        total_count = product_service.get_total_count(only_active=True)
        total_pages = formatter.calculate_total_pages(total_count)
        
        # Format message and inline keyboard (for product selection / pagination)
        message = formatter.format_product_list(products, current_page, total_pages, update)
        inline_keyboard = formatter.create_product_keyboard(products, current_page, total_pages, update)

        # Send main message with inline keyboard
        await update.message.reply_text(message, reply_markup=inline_keyboard)

        # Re-attach the reply keyboard in a lightweight follow-up message so that
        # the bottom custom keyboard (e.g. "🛒 Sản phẩm") stays visible after /products.
        #
        # Telegram only allows one type of keyboard per message (inline OR reply),
        # so we send a second small message that only carries the reply keyboard.
        try:
            hints_text = t("commands.help.interaction_hint", update)
            keyboard = get_persistent_keyboard(update)
            await update.message.reply_text(hints_text, reply_markup=keyboard)
        except Exception:
            # If anything goes wrong, we don't want to break the products flow
            pass
    except Exception as e:
        # Log error but don't fail the command
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in products command: {str(e)}", exc_info=True)
        await update.message.reply_text(t('commands.products.error', update))
    finally:
        session.close()


async def handle_products_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle Products button press from persistent keyboard.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    # Check if the message text matches the Products button text in any language
    if not update.message or not update.message.text:
        return  # Not a text message, ignore
    
    message_text = update.message.text.strip()
    
    # Get button text in current user's language
    products_text = t('buttons.products', update)
    
    # Also check common variations (in case of language mismatch)
    products_variations = [
        products_text,
        "🛒 Products",
        "🛒 Sản phẩm",
        "Products",
        "Sản phẩm"
    ]
    
    if message_text in products_variations:
        # Call the products command handler
        await products_command(update, context)
        # Handler processed the message, other handlers will still be called but handle_custom_quantity_input
        # will return early if user is not waiting for quantity input


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /lang or /language command - show language selection menu.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    user = update.effective_user
    user_id = user.id
    
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        preference_service = UserPreferenceService(session)
        current_language = preference_service.get_user_language(user_id)
        
        # Get language display names
        lang_display = t('languages.en', update) if current_language == 'en' else t('languages.vi', update)
        
        message = (
            f"{t('commands.language.title', update)}\n\n"
            f"{t('commands.language.current', update, lang_name=lang_display)}\n\n"
            f"{t('commands.language.select', update)}"
        )
        
        # Create language selection keyboard
        keyboard = [
            [
                InlineKeyboardButton(
                    t('languages.en', update),
                    callback_data="lang_en"
                ),
                InlineKeyboardButton(
                    t('languages.vi', update),
                    callback_data="lang_vi"
                ),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send language selection message with inline keyboard
        await update.message.reply_text(message, reply_markup=reply_markup)

        # Then re-send the persistent reply keyboard in a small follow-up message,
        # so the bottom custom keyboard (e.g. "🛒 Sản phẩm") comes back after /lang.
        try:
            keyboard_reply = get_persistent_keyboard(update)
            await update.message.reply_text(
                t("commands.start.help_hint", update),
                reply_markup=keyboard_reply,
            )
        except Exception:
            # Don't break /lang flow if keyboard restore fails
            pass
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in language command: {str(e)}", exc_info=True)
        await update.message.reply_text(t('commands.language.error', update))
    finally:
        session.close()

