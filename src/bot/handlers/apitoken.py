"""
Handler for the /apitoken command.

Generates (or regenerates) a per-user API token stored in BotUser.api_token.
The token can then be used with the /api/v1 dashboard endpoints via
`Authorization: Bearer <token>`.

Follows the project edit-message pattern: sends a new message (no prior
message to edit on a slash command).
"""

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.database.connection import get_session_factory
from src.database.services.bot_user_service import BotUserService
from src.bot.utils.language import t

logger = logging.getLogger(__name__)


async def apitoken_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /apitoken — generate or regenerate an API token for the calling user.
    """
    if not update.effective_user or not update.message:
        return

    user = update.effective_user
    telegram_user_id = user.id

    session_factory = get_session_factory()
    session = session_factory()
    try:
        svc = BotUserService(session)

        # Ensure the user exists in the database
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
