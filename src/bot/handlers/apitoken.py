"""
Handler for the /apitoken command and inline API management menu.

The /apitoken command generates (or regenerates) a per-user API token stored
in BotUser.api_token.  The inline menu (start_api callback) lets users view,
create, and revoke their token without leaving the chat.

API docs URL is read from the API_DOCS_URL environment variable.  When unset
the docs button is hidden rather than pointing to a dead link.
"""

import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.database.connection import get_session_factory
from src.database.services.bot_user_service import BotUserService
from src.bot.utils.language import t

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Keyboard helper
# ---------------------------------------------------------------------------

def _api_menu_keyboard(update: Update, has_token: bool) -> InlineKeyboardMarkup:
    """Build the API management inline keyboard."""
    api_docs_url = os.getenv("API_DOCS_URL", "")

    buttons = []
    if has_token:
        buttons.append([
            InlineKeyboardButton(t("api_menu.regenerate", update), callback_data="api_create"),
            InlineKeyboardButton(t("api_menu.revoke", update), callback_data="api_revoke"),
        ])
    else:
        buttons.append([
            InlineKeyboardButton(t("api_menu.create", update), callback_data="api_create"),
        ])

    if api_docs_url:
        buttons.append([
            InlineKeyboardButton(t("api_menu.docs", update), url=api_docs_url),
        ])

    buttons.append([
        InlineKeyboardButton(t("api_menu.back", update), callback_data="start_menu"),
    ])

    return InlineKeyboardMarkup(buttons)


def _api_menu_text(update: Update, token: str | None) -> str:
    """Build the API menu message text."""
    title = t("api_menu.title", update)
    if token:
        body = t("api_menu.has_token", update, token=token)
    else:
        body = t("api_menu.no_token", update)
    return f"{title}\n\n{body}"


# ---------------------------------------------------------------------------
# /apitoken command
# ---------------------------------------------------------------------------

async def apitoken_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /apitoken — generate or regenerate an API token for the calling user."""
    if not update.effective_user or not update.message:
        return

    user = update.effective_user
    telegram_user_id = user.id

    session_factory = get_session_factory()
    session = session_factory()
    try:
        svc = BotUserService(session)

        bot_user = svc.get_user_by_telegram_id(telegram_user_id)
        if not bot_user:
            await update.message.reply_text(
                t("apitoken.user_not_found", update),
                parse_mode=ParseMode.HTML,
            )
            return

        token = svc.generate_api_token(telegram_user_id)
        if token is None:
            await update.message.reply_text(
                t("apitoken.error", update),
                parse_mode=ParseMode.HTML,
            )
            return
    except Exception as exc:
        logger.error(
            "Error generating API token for user %s: %s",
            telegram_user_id,
            exc,
            exc_info=True,
        )
        await update.message.reply_text(
            t("apitoken.error", update),
            parse_mode=ParseMode.HTML,
        )
        return
    finally:
        session.close()

    await update.message.reply_text(
        t("apitoken.generated", update, token=token),
        parse_mode=ParseMode.HTML,
    )


# ---------------------------------------------------------------------------
# Inline API management callbacks
# ---------------------------------------------------------------------------

async def handle_api_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: start_api — show API token management view."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    session_factory = get_session_factory()
    session = session_factory()
    try:
        svc = BotUserService(session)
        bot_user = svc.get_user_by_telegram_id(user_id)
        if not bot_user:
            await query.edit_message_text(t("apitoken.user_not_found", update))
            return

        token = bot_user.api_token
        text = _api_menu_text(update, token)
        keyboard = _api_menu_keyboard(update, has_token=bool(token))
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    except Exception as exc:
        logger.error("Error showing API menu for user %s: %s", user_id, exc, exc_info=True)
        await query.answer(t("api_menu.error", update), show_alert=True)
    finally:
        session.close()


async def handle_api_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: api_create — create or regenerate the user's API token."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    session_factory = get_session_factory()
    session = session_factory()
    try:
        svc = BotUserService(session)
        token = svc.generate_api_token(user_id)
        if token is None:
            await query.answer(t("api_menu.error", update), show_alert=True)
            return

        text = _api_menu_text(update, token)
        keyboard = _api_menu_keyboard(update, has_token=True)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    except Exception as exc:
        logger.error("Error creating API token for user %s: %s", user_id, exc, exc_info=True)
        await query.answer(t("api_menu.error", update), show_alert=True)
    finally:
        session.close()


async def handle_api_revoke(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: api_revoke — revoke the user's API token."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    session_factory = get_session_factory()
    session = session_factory()
    try:
        svc = BotUserService(session)
        svc.revoke_api_token(user_id)

        text = _api_menu_text(update, token=None)
        keyboard = _api_menu_keyboard(update, has_token=False)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    except Exception as exc:
        logger.error("Error revoking API token for user %s: %s", user_id, exc, exc_info=True)
        await query.answer(t("api_menu.error", update), show_alert=True)
    finally:
        session.close()
