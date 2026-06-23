"""
Admin /set_emo flow: capture premium-emoji content for a placeholder.

Step 1: /set_emo <id>           -> mark state awaiting input for that placeholder
Step 2: next message (emoji)    -> read custom_emoji entities, store units
"""
import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.bot.handlers.commands import state_manager
from src.bot.messages.emoji_renderer import parse_emoji_units
from src.bot.utils.admin_check import is_admin
from src.bot.utils.language import t
from src.database.connection import get_session_factory
from src.database.services.emoji_placeholder_service import EmojiPlaceholderService

logger = logging.getLogger(__name__)


def extract_units_from_message(message) -> list:
    """Pure helper: build unit list from a message-like object."""
    return parse_emoji_units(getattr(message, "text", "") or "", getattr(message, "entities", []) or [])


async def set_emo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/set_emo <id> — begin capturing emoji for a placeholder (admins only)."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text(t("commands.set_emo.no_permission", update))
        return

    args = context.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_text(t("commands.set_emo.usage", update))
        return

    placeholder_id = int(args[0])
    session = get_session_factory()()
    try:
        svc = EmojiPlaceholderService(session)
        row = svc.get(placeholder_id)
        if row is None:
            await update.message.reply_text(
                t("commands.set_emo.not_found", update, id=placeholder_id)
            )
            return
        name = row.name
    finally:
        session.close()

    state = state_manager.get_user_state(user.id)
    if state is None:
        from src.bot.states.state_manager import UserState
        state = UserState()
    state.awaiting_emoji_input = True
    state.pending_emoji_placeholder_id = placeholder_id
    state_manager.set_user_state(user.id, state)

    await update.message.reply_text(
        t("commands.set_emo.prompt", update, id=placeholder_id, name=name)
    )


async def handle_emoji_capture(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Second step: capture the emoji message that follows /set_emo."""
    user = update.effective_user
    message = update.message
    if not user or not message:
        return

    state = state_manager.get_user_state(user.id)
    if not state or not state.awaiting_emoji_input:
        return  # not in capture mode; let other handlers deal with it

    if not is_admin(user.id):
        return

    placeholder_id = state.pending_emoji_placeholder_id
    units = extract_units_from_message(message)

    state.awaiting_emoji_input = False
    state.pending_emoji_placeholder_id = None
    state_manager.set_user_state(user.id, state)

    emoji_count = sum(1 for u in units if u.get("t") == "emoji")
    if emoji_count == 0:
        await message.reply_text(t("commands.set_emo.no_emoji", update))
        return

    session = get_session_factory()()
    try:
        svc = EmojiPlaceholderService(session)
        svc.set_content(
            placeholder_id, units, raw_text=message.text or "", set_by=user.id
        )
    except ValueError:
        await message.reply_text(
            t("commands.set_emo.gone", update, id=placeholder_id)
        )
        return
    finally:
        session.close()

    await message.reply_text(
        t("commands.set_emo.captured", update, count=emoji_count, id=placeholder_id)
    )
