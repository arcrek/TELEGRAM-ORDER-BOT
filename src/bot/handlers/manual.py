"""Manual (user guide) bot handlers."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.database.connection import get_session_factory
from src.database.services.manual_service import ManualService
from src.bot.handlers.callbacks import state_manager
from src.bot.utils.language import t

logger = logging.getLogger(__name__)


async def handle_manual_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show list of manuals for a product."""
    query = update.callback_query
    await query.answer()
    data = query.data  # "manual_list_{product_id}"
    product_id = data.replace("manual_list_", "", 1)

    session_factory = get_session_factory()
    session = session_factory()
    try:
        service = ManualService(session)
        manuals = service.list_manuals_by_product(product_id, only_active=True)

        keyboard = []
        if manuals:
            for manual in manuals:
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            manual.title, callback_data=f"manual_view_{manual.id}"
                        )
                    ]
                )
            header = t("manual.list_title", update)
        else:
            header = t("manual.empty", update)

        back_text = t("manual.back_to_list", update)
        keyboard.append(
            [InlineKeyboardButton(back_text, callback_data=f"product_{product_id}")]
        )

        await query.edit_message_text(
            header, reply_markup=InlineKeyboardMarkup(keyboard)
        )
    finally:
        session.close()


async def handle_manual_view(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show full content of a single manual."""
    query = update.callback_query
    await query.answer()
    data = query.data  # "manual_view_{manual_id}"
    manual_id = data.replace("manual_view_", "", 1)

    user_id = update.effective_user.id
    user_state = state_manager.get_user_state(user_id)
    product_id = user_state.selected_product_id if user_state else None

    session_factory = get_session_factory()
    session = session_factory()
    try:
        service = ManualService(session)
        manual = service.get_manual_by_id(manual_id)

        if not manual:
            await query.edit_message_text("❌ Guide not found.")
            return

        text = f"{manual.title}\n\n{manual.content}"

        back_text = t("manual.back_to_list", update)
        if product_id:
            back_cb = f"manual_list_{product_id}"
        else:
            back_cb = "back_to_list"

        keyboard = [[InlineKeyboardButton(back_text, callback_data=back_cb)]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    finally:
        session.close()
