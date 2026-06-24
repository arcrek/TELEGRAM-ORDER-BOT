"""
Command handlers for the Telegram bot.
"""

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.database.connection import get_session_factory
from src.database.services.product_service import ProductService
from src.database.services.bot_user_service import BotUserService
from src.database.services.order_service import OrderService
from src.database.services.statistics_service import StatisticsService
from src.database.models.enums import OrderStatus
from src.database.services.user_preference_service import UserPreferenceService
from src.bot.utils.admin_check import (
    GLOBAL_ADMIN_ID,
    add_admin,
    get_admin_telegram_ids,
    is_admin,
    remove_admin,
)
from src.database.services.bot_ui_settings_service import BotUiSettingsService
from src.database.services.pre_uploaded_service import PreUploadedService
from src.bot.messages.product_formatter import ProductFormatter
from src.bot.states.state_manager import StateManager
from src.bot.utils.language import t
from src.bot.utils.keyboard import get_persistent_keyboard
from src.database.services.app_settings_service import AppSettingsService
from src.utils.datetime_format import resolve_tz, now_local
from src.bot.messages.emoji_renderer import render as render_emoji
from src.database.services.emoji_placeholder_service import EmojiPlaceholderService
from src.database.services.block_service import BlockService


# Global state manager instance
state_manager = StateManager()


def _get_bot_selection_prompts(session) -> tuple[str | None, str | None]:
    """Load global custom prompt texts for product/variation selection."""
    service = BotUiSettingsService(session)
    settings = service.get_settings()
    return settings.product_choose_text, settings.variation_choose_text


async def _restore_reply_keyboard(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
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
        sent = await context.bot.send_message(
            chat_id=chat_id, text="\u200b", reply_markup=keyboard
        )
        try:
            await context.bot.delete_message(
                chat_id=chat_id, message_id=sent.message_id
            )
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


def _start_inline_keyboard(update: Update) -> InlineKeyboardMarkup:
    """Build the start menu inline keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t("buttons.products", update), callback_data="start_products"
                ),
                InlineKeyboardButton(
                    t("buttons.balance", update), callback_data="balance_view"
                ),
            ],
            [
                InlineKeyboardButton(
                    t("buttons.order_history", update), callback_data="start_history"
                ),
                InlineKeyboardButton(
                    t("start_menu.api_button", update), callback_data="start_api"
                ),
            ],
            [
                InlineKeyboardButton(
                    t("buttons.export", update), callback_data="start_export"
                ),
            ],
        ]
    )


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

    # Get system name from environment
    system_name = os.getenv("SYSTEM_NAME", "MUATAIKHOANPRO")

    welcome_message = (
        f"{t('commands.start.welcome', update, name=user.first_name or 'User')}\n\n"
        f"{t('commands.start.description', update, system_name=system_name)}\n"
        f"{t('commands.start.help_hint', update)}"
    )
    # Send welcome text with the reply keyboard, then send the inline menu
    keyboard = get_persistent_keyboard(update)
    await update.message.reply_text(welcome_message, reply_markup=keyboard)

    menu_title = t("start_menu.title", update)
    inline_kb = _start_inline_keyboard(update)
    await update.message.reply_text(menu_title, reply_markup=inline_kb)


async def handle_start_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: start_menu — restore the 4-button start inline keyboard (used as back button)."""
    query = update.callback_query
    await query.answer()
    menu_title = t("start_menu.title", update)
    await query.edit_message_text(
        menu_title, reply_markup=_start_inline_keyboard(update)
    )


async def handle_start_products(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Callback: start_products — show product list from the start menu."""
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

        products = product_service.list_products(
            page=1, per_page=9999, only_active=True
        )

        pre_uploaded_service = PreUploadedService(session)
        pre_uploaded_in_stock_ids = pre_uploaded_service.get_in_stock_product_ids(
            [p.id for p in products]
        )

        message = formatter.format_product_list(product_choose_text=product_choose_text)
        inline_keyboard = formatter.create_product_keyboard(
            products,
            update,
            pre_uploaded_in_stock_ids=pre_uploaded_in_stock_ids,
            emoji_service=EmojiPlaceholderService(session),
        )
        rendered, parse_mode = render_emoji(message, EmojiPlaceholderService(session))
        await query.edit_message_text(
            rendered, reply_markup=inline_keyboard, parse_mode=parse_mode
        )
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error in handle_start_products: {str(e)}", exc_info=True)
        await query.edit_message_text(t("commands.products.error", update))
    finally:
        session.close()


async def handle_start_history(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Callback: start_history — show order history from the start menu."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    session_factory = get_session_factory()
    session = session_factory()
    try:
        order_service = OrderService(session)
        orders = order_service.get_user_orders(
            user_id, status=OrderStatus.DELIVERED, limit=200
        )

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
            status_val = (
                order.status.value
                if hasattr(order.status, "value")
                else str(order.status)
            )
            emoji = status_emoji.get(status_val, "❓")
            label = f"#{order.id} | {emoji} | {order.total_amount:,}đ"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        label, callback_data=f"order_detail_{order.id}_from_{page}"
                    )
                ]
            )

        nav_row = []
        if page < total_pages:
            next_text = t("buttons.next", update)
            nav_row.append(
                InlineKeyboardButton(
                    next_text, callback_data=f"order_history_page_{page + 1}"
                )
            )
        if nav_row:
            keyboard.append(nav_row)

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error in handle_start_history: {str(e)}", exc_info=True)
        await query.edit_message_text(t("order_history.error", update))
    finally:
        session.close()


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
        f"{t('commands.help.products', update)}\n"
        f"{t('commands.help.balance', update)}\n\n"
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

        products = product_service.list_products(
            page=1, per_page=9999, only_active=True
        )

        pre_uploaded_service = PreUploadedService(session)
        pre_uploaded_in_stock_ids = pre_uploaded_service.get_in_stock_product_ids(
            [p.id for p in products]
        )

        message = formatter.format_product_list(product_choose_text=product_choose_text)
        inline_keyboard = formatter.create_product_keyboard(
            products,
            update,
            pre_uploaded_in_stock_ids=pre_uploaded_in_stock_ids,
            emoji_service=EmojiPlaceholderService(session),
        )

        # Send main message with inline keyboard
        rendered, parse_mode = render_emoji(message, EmojiPlaceholderService(session))
        await update.message.reply_text(
            rendered, reply_markup=inline_keyboard, parse_mode=parse_mode
        )

        # Restore reply keyboard without leaving a message
        await _restore_reply_keyboard(update, context)
    except Exception as e:
        # Log error but don't fail the command
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error in products command: {str(e)}", exc_info=True)
        await update.message.reply_text(t("commands.products.error", update))
    finally:
        session.close()


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /balance command — show balance wallet view."""
    user = update.effective_user

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
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error tracking user in /balance: {str(e)}", exc_info=True)
    finally:
        session.close()

    from src.bot.handlers.balance import handle_balance_button

    await handle_balance_button(update, context)


_ORDERS_PER_PAGE = 8


async def order_history_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
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
        orders = order_service.get_user_orders(
            user_id, status=OrderStatus.DELIVERED, limit=200
        )

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
            status_val = (
                order.status.value
                if hasattr(order.status, "value")
                else str(order.status)
            )
            emoji = status_emoji.get(status_val, "❓")
            label = f"#{order.id} | {emoji} | {order.total_amount:,}đ"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        label, callback_data=f"order_detail_{order.id}_from_{page}"
                    )
                ]
            )

        nav_row = []
        if page < total_pages:
            next_text = t("buttons.next", update)
            nav_row.append(
                InlineKeyboardButton(
                    next_text, callback_data=f"order_history_page_{page + 1}"
                )
            )
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


async def handle_products_button(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
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
    top_buyers_text = t("buttons.top_buyers", update)

    # Also check common variations (in case user switched language)
    api_text = t("start_menu.api_button", update)

    products_variations = {
        products_text,
        "🛒 Products",
        "🛒 Sản phẩm",
        "Products",
        "Sản phẩm",
    }
    language_variations = {
        language_text,
        "🌐 Language",
        "🌐 Ngôn ngữ",
        "Language",
        "Ngôn ngữ",
    }
    order_history_variations = {
        order_history_text,
        "📋 Order History",
        "📋 Đơn hàng đã mua",
    }
    balance_variations = {balance_text, "💰 Balance", "💰 Số dư"}
    top_buyers_variations = {
        top_buyers_text,
        "🏆 Top buyers today",
        "🏆 Top mua hôm nay",
    }
    api_variations = {api_text, "🔑 API"}

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

    if message_text in top_buyers_variations:
        await handle_top_buyers_button(update, context)
        return

    if message_text in api_variations:
        from src.bot.handlers.apitoken import api_command

        await api_command(update, context)
        return

    export_text = t("buttons.export", update)
    export_variations = {export_text, "📤 Export", "📤 Xuất dữ liệu"}
    if message_text in export_variations:
        from src.bot.handlers.export import export_command

        await export_command(update, context)
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
        lang_display = (
            t("languages.en", update)
            if current_language == "en"
            else t("languages.vi", update)
        )

        message = (
            f"{t('commands.language.title', update)}\n\n"
            f"{t('commands.language.current', update, lang_name=lang_display)}\n\n"
            f"{t('commands.language.select', update)}"
        )

        # Create language selection keyboard
        keyboard = [
            [
                InlineKeyboardButton(
                    t("languages.en", update), callback_data="lang_en"
                ),
                InlineKeyboardButton(
                    t("languages.vi", update), callback_data="lang_vi"
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
        await update.message.reply_text(t("commands.language.error", update))
    finally:
        session.close()


async def _resolve_admin_target(arg: str, update: Update) -> Optional[int]:
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
                t(
                    "commands.setadmin.user_not_found",
                    update,
                    username=arg if arg.startswith("@") else f"@{arg}",
                )
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
                uname = (
                    f" (@{bot_user.username})" if bot_user and bot_user.username else ""
                )
                source = (
                    " [super]"
                    if uid == GLOBAL_ADMIN_ID
                    else (" [env]" if uid not in db_records else "")
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


async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /block <id|@username> — block a user (admin only)."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text(t("commands.block.no_permission", update))
        return

    args = context.args or []
    if not args:
        await update.message.reply_text(t("commands.block.usage", update))
        return

    identifier = args[0]
    session_factory = get_session_factory()
    session = session_factory()
    try:
        try:
            BlockService(session).block(identifier)
        except ValueError:
            await update.message.reply_text(t("commands.block.usage", update))
            return
    finally:
        session.close()
    await update.message.reply_text(
        t("commands.block.blocked", update, target=identifier)
    )


async def unblock_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /unblock <id|@username> — unblock a user (admin only)."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text(t("commands.block.no_permission", update))
        return

    args = context.args or []
    if not args:
        await update.message.reply_text(t("commands.block.usage", update))
        return

    identifier = args[0]
    session_factory = get_session_factory()
    session = session_factory()
    try:
        try:
            removed = BlockService(session).unblock(identifier)
        except ValueError:
            await update.message.reply_text(t("commands.block.usage", update))
            return
    finally:
        session.close()
    if removed:
        await update.message.reply_text(
            t("commands.block.unblocked", update, target=identifier)
        )
    else:
        await update.message.reply_text(
            t("commands.block.not_blocked", update, target=identifier)
        )


def _mask_name(name: str) -> str:
    """Mask a name/username, keeping first and last char with stars in between."""
    if not name:
        return "***"
    if len(name) == 1:
        return name[0] + "*"
    if len(name) == 2:
        return name[0] + "*"
    return name[0] + "*" * (len(name) - 2) + name[-1]


async def handle_top_buyers_button(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle Top Buyers button — shows top 5 users by spending today."""
    if not update.message:
        return

    user = update.effective_user
    user_id = user.id if user else None
    caller_is_admin = is_admin(user_id) if user_id else False

    session_factory = get_session_factory()
    session = session_factory()
    try:
        service = StatisticsService(session)
        buyers = service.get_top_buyers_today(limit=5)
    finally:
        session.close()

    title = t("top_buyers.title", update)
    if not buyers:
        text = f"{title}\n\n{t('top_buyers.empty', update)}"
    else:
        lines = [title, ""]
        for i, buyer in enumerate(buyers, start=1):
            first = buyer["first_name"]
            last = buyer["last_name"]
            username = buyer["username"]
            full_name = f"{first} {last}".strip() or "User"

            if caller_is_admin:
                name_display = full_name
                if username:
                    name_display += f" (@{username})"
            else:
                masked = _mask_name(full_name)
                name_display = masked

            total_fmt = f"{buyer['total_spent']:,}".replace(",", ".")
            entry = t(
                "top_buyers.entry",
                update,
                rank=i,
                name=name_display,
                total=total_fmt,
                count=buyer["order_count"],
            )
            lines.append(entry)
        text = "\n".join(lines)

    await update.message.reply_text(text, parse_mode=None)


async def doanhthu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/doanhthu [YYYY-MM-DD] — show revenue for a day (admin only)."""
    if not update.message:
        return

    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("⛔ Chỉ admin mới dùng được lệnh này.")
        return

    # Parse optional date argument; default to today in app timezone
    args = context.args or []
    session_factory = get_session_factory()
    session = session_factory()
    try:
        app_tz = resolve_tz(AppSettingsService(session).get_settings().timezone)
        now_app = now_local(app_tz)

        if args:
            raw = args[0].strip()
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
                await update.message.reply_text(
                    "❌ Định dạng ngày không hợp lệ. Dùng: /doanhthu YYYY-MM-DD"
                )
                return
            try:
                parsed = datetime.strptime(raw, "%Y-%m-%d")
                # Interpret input as a local calendar day in app timezone
                target = datetime(parsed.year, parsed.month, parsed.day, tzinfo=app_tz)
            except ValueError:
                await update.message.reply_text("❌ Ngày không hợp lệ.")
                return
        else:
            target = now_app.replace(hour=0, minute=0, second=0, microsecond=0)

        # Build UTC range covering the full calendar day in app timezone
        # Statistics service expects naive-UTC datetimes
        day_start_utc = target.astimezone(timezone.utc).replace(tzinfo=None)
        day_end_utc = (
            (target + timedelta(days=1)).astimezone(timezone.utc).replace(tzinfo=None)
        )

        service = StatisticsService(session)
        revenue = service.get_total_revenue(
            start_date=day_start_utc, end_date=day_end_utc
        )
        order_count = service.get_total_orders_count(
            start_date=day_start_utc, end_date=day_end_utc
        )
        by_status = service.get_orders_by_status(
            start_date=day_start_utc, end_date=day_end_utc
        )
    finally:
        session.close()

    date_label = target.strftime("%d/%m/%Y")
    revenue_fmt = f"{revenue:,}".replace(",", ".")
    paid = by_status.get("paid", 0) + by_status.get("delivered", 0)
    pending = by_status.get("pending", 0)
    cancelled = by_status.get("cancelled", 0)

    text = (
        f"📊 DOANH THU NGÀY {date_label}\n\n"
        f"💰 Tổng doanh thu: {revenue_fmt} VND\n"
        f"📦 Tổng đơn hàng: {order_count}\n"
        f"  ✅ Đã thanh toán/giao: {paid}\n"
        f"  ⏳ Chờ thanh toán: {pending}\n"
        f"  ❌ Đã hủy: {cancelled}"
    )
    await update.message.reply_text(text)
