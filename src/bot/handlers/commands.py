"""
Command handlers for the Telegram bot.
"""
import os
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.database.connection import get_session_factory
from src.database.services.product_service import ProductService
from src.database.services.bot_user_service import BotUserService
from src.database.services.order_service import OrderService
from src.database.models.enums import OrderStatus
from src.database.services.user_preference_service import UserPreferenceService
from src.bot.utils.admin_check import GLOBAL_ADMIN_ID, add_admin, get_admin_telegram_ids, is_admin, remove_admin
from src.database.services.bot_ui_settings_service import BotUiSettingsService
from src.bot.messages.product_formatter import ProductFormatter
from src.bot.states.state_manager import StateManager
from src.bot.utils.language import get_user_language, t
from src.bot.utils.keyboard import get_persistent_keyboard


# Global state manager instance
state_manager = StateManager()


def _get_bot_selection_prompts(session) -> tuple[str | None, str | None]:
    """Load global custom prompt texts for product/variation selection."""
    service = BotUiSettingsService(session)
    settings = service.get_settings()
    return settings.product_choose_text, settings.variation_choose_text

async def _restore_reply_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Restore the reply-keyboard without leaving an extra message in chat.

    Telegram clients keep showing the latest reply keyboard until it is replaced/removed.
    We exploit that by sending a tiny message that sets the keyboard, then deleting it.
    """
    if not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    keyboard = get_persistent_keyboard(update)

    try:
        # Use a zero-width space so the message is "non-empty" but visually blank.
        sent = await context.bot.send_message(chat_id=chat_id, text="\u200B", reply_markup=keyboard)
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=sent.message_id)
        except Exception:
            # If deletion fails (permissions, timing), it's harmless.
            pass
    except Exception:
        # Never break the main flow just because keyboard restore failed.
        pass

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle any unknown "/" command.

    This is mainly used to re-attach the reply keyboard if the client hides it
    after the user sends an unrecognized command (e.g. sending just "/").
    """
    if not update.message:
        return

    await _restore_reply_keyboard(update, context)


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
    
    # Get system name from environment
    system_name = os.getenv("SYSTEM_NAME", "MUATAIKHOANPRO")
    
    welcome_message = (
        f"{t('commands.start.welcome', update, name=user.first_name or 'User')}\n\n"
        f"{t('commands.start.description', update, system_name=system_name)}\n"
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
            f"{t('commands.help.notify_active', update)}\n"
            f"{t('commands.help.setadmin', update)}"
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
        
        # Get products
        product_service = ProductService(session)
        formatter = ProductFormatter()
        product_choose_text, _ = _get_bot_selection_prompts(session)

        products = product_service.list_products(page=1, per_page=9999, only_active=True)

        message = formatter.format_product_list(product_choose_text=product_choose_text)
        inline_keyboard = formatter.create_product_keyboard(products, update)

        # Send main message with inline keyboard
        await update.message.reply_text(message, reply_markup=inline_keyboard)

        # Restore reply keyboard without leaving a message
        await _restore_reply_keyboard(update, context)
    except Exception as e:
        # Log error but don't fail the command
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in products command: {str(e)}", exc_info=True)
        await update.message.reply_text(t('commands.products.error', update))
    finally:
        session.close()


_ORDERS_PER_PAGE = 8


async def order_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /orders command and reply-keyboard 'Order History' button."""
    user = update.effective_user
    user_id = user.id

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

        order_service = OrderService(session)
        orders = order_service.get_user_orders(user_id, status=OrderStatus.DELIVERED, limit=200)

        total = len(orders)
        total_pages = max(1, (total + _ORDERS_PER_PAGE - 1) // _ORDERS_PER_PAGE)
        page = 1
        page_orders = orders[:_ORDERS_PER_PAGE]

        status_emoji = {
            "pending": "⏳",
            "paid": "✅",
            "processing": "🔄",
            "delivered": "📦",
            "cancelled": "❌",
        }

        title = t("order_history.title", update)
        if total == 0:
            body = t("order_history.empty", update)
        else:
            body = t("order_history.count", update, count=total)

        message = f"{title}\n\n{body}"

        keyboard = []
        for order in page_orders:
            status_val = order.status.value if hasattr(order.status, "value") else str(order.status)
            emoji = status_emoji.get(status_val, "❓")
            label = f"#{order.id} | {emoji} | {order.total_amount:,}đ"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"order_detail_{order.id}_from_{page}")])

        nav_row = []
        if page < total_pages:
            next_text = t("buttons.next", update)
            nav_row.append(InlineKeyboardButton(next_text, callback_data=f"order_history_page_{page + 1}"))
        if nav_row:
            keyboard.append(nav_row)

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(message, reply_markup=reply_markup)
        await _restore_reply_keyboard(update, context)

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in order_history_command: {str(e)}", exc_info=True)
        await update.message.reply_text(t("order_history.error", update))
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
    
    # Reply-keyboard buttons
    products_text = t("buttons.products", update)
    language_text = t("buttons.language", update)
    order_history_text = t("buttons.order_history", update)
    balance_text = t("buttons.balance", update)

    # Also check common variations (in case user switched language)
    products_variations = {products_text, "🛒 Products", "🛒 Sản phẩm", "Products", "Sản phẩm"}
    language_variations = {language_text, "🌐 Language", "🌐 Ngôn ngữ", "Language", "Ngôn ngữ"}
    order_history_variations = {order_history_text, "📋 Order History", "📋 Đơn hàng đã mua"}
    balance_variations = {balance_text, "💰 Balance", "💰 Số dư"}

    if message_text in products_variations:
        await products_command(update, context)
        return

    if message_text in order_history_variations:
        await order_history_command(update, context)
        return

    if message_text in balance_variations:
        from src.bot.handlers.balance import handle_balance_button
        await handle_balance_button(update, context)
        return

    if message_text in language_variations:
        await language_command(update, context)
        return


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

        # Restore reply keyboard without leaving a message
        await _restore_reply_keyboard(update, context)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in language command: {str(e)}", exc_info=True)
        await update.message.reply_text(t('commands.language.error', update))
    finally:
        session.close()


async def _resolve_admin_target(
    arg: str, update: Update
) -> Optional[int]:
    """
    Resolve a /setadmin argument to a Telegram user ID.

    Accepts:
      - A numeric ID (e.g. "123456789")
      - A @username or bare username (looked up in bot_users DB)

    Returns the numeric Telegram user ID, or None if resolution failed
    (an error reply is already sent in that case).
    """
    is_username = arg.startswith("@") or not arg.lstrip("-").lstrip("+").isdigit()
    if is_username:
        username = arg.lstrip("@")
        session_factory = get_session_factory()
        session = session_factory()
        try:
            bot_user = BotUserService(session).get_user_by_username(username)
        finally:
            session.close()
        if not bot_user:
            await update.message.reply_text(
                t("commands.setadmin.user_not_found", update, username=arg if arg.startswith("@") else f"@{arg}")
            )
            return None
        return bot_user.telegram_user_id
    else:
        try:
            return int(arg)
        except ValueError:
            await update.message.reply_text(t("commands.setadmin.invalid_id", update))
            return None


async def setadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /setadmin command — manage dynamic admin list.

    Usage:
      /setadmin list                        — show current admins (all admins)
      /setadmin <id|@username>              — add a new admin (super admin only)
      /setadmin remove <id|@username>       — remove an admin (super admin only)

    All admins can run 'list'. Add/remove is restricted to the super admin.
    """
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text(t("commands.setadmin.no_permission", update))
        return

    args = context.args or []
    is_super_admin = user.id == GLOBAL_ADMIN_ID

    # ── list ──────────────────────────────────────────────────────────────────
    if not args or args[0].lower() == "list":
        session_factory = get_session_factory()
        session = session_factory()
        try:
            from src.database.services.bot_admin_service import BotAdminService
            bot_svc = BotUserService(session)
            ba_svc = BotAdminService(session)
            db_records = {r.telegram_user_id: r for r in ba_svc.list_all()}

            lines = []
            for uid in get_admin_telegram_ids():
                bot_user = bot_svc.get_user_by_telegram_id(uid)
                uname = f" (@{bot_user.username})" if bot_user and bot_user.username else ""
                source = " [super]" if uid == GLOBAL_ADMIN_ID else (
                    " [env]" if uid not in db_records else ""
                )
                lines.append(f"• {uid}{uname}{source}")
        finally:
            session.close()
        await update.message.reply_text(
            t("commands.setadmin.list", update, ids="\n".join(lines) or "—")
        )
        return

    # ── add / remove — super admin only ───────────────────────────────────────
    if not is_super_admin:
        await update.message.reply_text(t("commands.setadmin.no_permission", update))
        return

    if args[0].lower() == "remove":
        if len(args) < 2:
            await update.message.reply_text(t("commands.setadmin.usage", update))
            return
        target_id = await _resolve_admin_target(args[1], update)
        if target_id is None:
            return
        if remove_admin(target_id):
            await update.message.reply_text(
                t("commands.setadmin.removed", update, user_id=target_id)
            )
        else:
            await update.message.reply_text(
                t("commands.setadmin.not_found_or_protected", update, user_id=target_id)
            )
        return

    # Default: add
    target_id = await _resolve_admin_target(args[0], update)
    if target_id is None:
        return
    if add_admin(target_id, added_by=user.id):
        await update.message.reply_text(
            t("commands.setadmin.added", update, user_id=target_id)
        )
    else:
        await update.message.reply_text(
            t("commands.setadmin.already_admin", update, user_id=target_id)
        )

