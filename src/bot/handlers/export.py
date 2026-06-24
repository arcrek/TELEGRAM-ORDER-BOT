"""
Customer /export flow.

Pick a product, toggle one or more of its variants, then receive one .txt per
variant containing every delivered pre-uploaded order for that product+variant.
Selection menus edit in place; the .txt files are sent as new documents.
"""
import logging
from io import BytesIO

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.bot.handlers.commands import state_manager
from src.bot.messages.emoji_renderer import render as render_emoji, split_icon
from src.bot.messages.export_formatter import build_variant_file
from src.bot.states.state_manager import UserState
from src.bot.utils.language import t
from src.database.connection import get_session_factory
from src.database.services.app_settings_service import AppSettingsService
from src.database.services.emoji_placeholder_service import EmojiPlaceholderService
from src.database.services.export_service import ExportService
from src.utils.datetime_format import resolve_tz

logger = logging.getLogger(__name__)


def _export_labels(update: Update) -> dict:
    """Resolve the in-file labels (no kwargs → templates returned raw)."""
    return {
        "totals": t("commands.export.file_totals", update),
        "order": t("commands.export.file_order", update),
        "date": t("commands.export.file_date", update),
        "price": t("commands.export.file_price", update),
        "qty": t("commands.export.file_qty", update),
        "delivered": t("commands.export.file_delivered", update),
        "vnd": t("commands.export.file_vnd", update),
    }


def _btn_label_icon(name: str, emoji_service):
    """Resolve a {emo:id} token in a name to (clean_label, icon_custom_emoji_id)."""
    if emoji_service is None:
        return name, None
    return split_icon(name, emoji_service)


def _product_list_keyboard(products: list, update: Update, emoji_service=None) -> InlineKeyboardMarkup:
    rows = []
    for i, p in enumerate(products):
        label, icon = _btn_label_icon(p["name"], emoji_service)
        rows.append([InlineKeyboardButton(label, callback_data=f"export_prod_{i}",
                                          icon_custom_emoji_id=icon)])
    rows.append([InlineKeyboardButton(t("buttons.cancel", update),
                                      callback_data="export_cancel")])
    return InlineKeyboardMarkup(rows)


def _variant_keyboard(variations: list, selected: set, update: Update, emoji_service=None) -> InlineKeyboardMarkup:
    rows = []
    for i, v in enumerate(variations):
        mark = "✅ " if v["id"] in selected else "▫️ "
        label, icon = _btn_label_icon(v["name"], emoji_service)
        rows.append([InlineKeyboardButton(f"{mark}{label}",
                                          callback_data=f"export_var_{i}",
                                          icon_custom_emoji_id=icon)])
    rows.append([InlineKeyboardButton(t("commands.export.export_button", update),
                                      callback_data="export_go")])
    rows.append([
        InlineKeyboardButton(t("buttons.back", update), callback_data="export_back"),
        InlineKeyboardButton(t("buttons.cancel", update), callback_data="export_cancel"),
    ])
    return InlineKeyboardMarkup(rows)


def _product_list_keyboard_emoji(products: list, update: Update) -> InlineKeyboardMarkup:
    """Product-list keyboard with custom-emoji button icons (own short session)."""
    session = get_session_factory()()
    try:
        return _product_list_keyboard(products, update, EmojiPlaceholderService(session))
    finally:
        session.close()


def _variant_view(text: str, variations: list, selected: set, update: Update):
    """Render the choose-variants message text and build the variant keyboard
    (with custom-emoji button icons) in a single short session.

    Returns (rendered_text, parse_mode, keyboard).
    """
    session = get_session_factory()()
    try:
        svc = EmojiPlaceholderService(session)
        rendered, parse_mode = render_emoji(text, svc)
        keyboard = _variant_keyboard(variations, selected, update, svc)
        return rendered, parse_mode, keyboard
    finally:
        session.close()


async def _render_product_list(update: Update, user_id: int, *, edit: bool) -> None:
    session = get_session_factory()()
    try:
        products = ExportService(session).get_exportable_products(user_id)
    finally:
        session.close()

    if not products:
        text = t("commands.export.empty", update)
        if edit and update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        state_manager.clear_user_state(user_id)
        return

    state = state_manager.get_user_state(user_id) or UserState()
    state.export_products = products
    state.export_product_id = None
    state.export_variations = []
    state.export_selected_variation_ids = set()
    state_manager.set_user_state(user_id, state)

    text = t("commands.export.choose_product", update)
    kb = _product_list_keyboard_emoji(products, update)
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/export entry point."""
    if not update.message:
        return
    await _render_product_list(update, update.effective_user.id, edit=False)


async def handle_export_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback start_export — from the /start inline menu."""
    query = update.callback_query
    await query.answer()
    await _render_product_list(update, query.from_user.id, edit=True)


async def handle_export_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback export_prod_<idx> — show variant multi-select."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = state_manager.get_user_state(user_id)
    if not state or not state.export_products:
        await query.edit_message_text(t("commands.export.expired", update))
        return
    try:
        idx = int((query.data or "").rsplit("_", 1)[1])
        product = state.export_products[idx]
    except (ValueError, IndexError):
        await query.edit_message_text(t("commands.export.expired", update))
        return

    session = get_session_factory()()
    try:
        variations = ExportService(session).get_exportable_variations(user_id, product["id"])
    finally:
        session.close()

    state.export_product_id = product["id"]
    state.export_variations = variations
    state.export_selected_variation_ids = set()
    state_manager.set_user_state(user_id, state)

    text = t("commands.export.choose_variants", update, product=product["name"])
    rendered, parse_mode, kb = _variant_view(text, variations, set(), update)
    await query.edit_message_text(rendered, reply_markup=kb, parse_mode=parse_mode)


async def handle_export_variant_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback export_var_<idx> — toggle a variant selection in place."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = state_manager.get_user_state(user_id)
    if not state or not state.export_variations:
        await query.edit_message_text(t("commands.export.expired", update))
        return
    try:
        idx = int((query.data or "").rsplit("_", 1)[1])
        var_id = state.export_variations[idx]["id"]
    except (ValueError, IndexError):
        await query.edit_message_text(t("commands.export.expired", update))
        return

    selected = set(state.export_selected_variation_ids)
    selected ^= {var_id}
    state.export_selected_variation_ids = selected
    state_manager.set_user_state(user_id, state)

    product_name = next(
        (p["name"] for p in state.export_products if p["id"] == state.export_product_id), ""
    )
    text = t("commands.export.choose_variants", update, product=product_name)
    rendered, parse_mode, kb = _variant_view(text, state.export_variations, selected, update)
    await query.edit_message_text(rendered, reply_markup=kb, parse_mode=parse_mode)


async def handle_export_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback export_back — return to the product list."""
    query = update.callback_query
    await query.answer()
    await _render_product_list(update, query.from_user.id, edit=True)


async def handle_export_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback export_cancel — clear state and close."""
    query = update.callback_query
    await query.answer()
    state_manager.clear_user_state(query.from_user.id)
    await query.edit_message_text(t("commands.export.cancelled", update))


async def handle_export_generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback export_go — build and send one .txt per selected variant."""
    query = update.callback_query
    user_id = query.from_user.id
    state = state_manager.get_user_state(user_id)
    if not state or not state.export_product_id or not state.export_selected_variation_ids:
        # Answer with an alert (do NOT answer() before this branch).
        await query.answer(t("commands.export.none_selected", update), show_alert=True)
        return
    await query.answer()

    labels = _export_labels(update)
    product_id = state.export_product_id
    selected = list(state.export_selected_variation_ids)

    session = get_session_factory()()
    sent = 0
    try:
        service = ExportService(session)
        tz = resolve_tz(AppSettingsService(session).get_settings().timezone)
        for variation_id in selected:
            data = service.get_variant_export(user_id, product_id, variation_id)
            if data is None:
                continue
            filename, content = build_variant_file(data, labels, tz)
            file_obj = BytesIO(content.encode("utf-8"))
            file_obj.name = filename
            try:
                await context.bot.send_document(
                    chat_id=user_id, document=file_obj, filename=filename
                )
                sent += 1
            except Exception as e:
                logger.error(f"Export send_document failed for {filename}: {e}", exc_info=True)
    finally:
        session.close()

    state_manager.clear_user_state(user_id)
    if sent == 0:
        await query.edit_message_text(t("commands.export.none_exported", update))
    else:
        await query.edit_message_text(t("commands.export.done", update, count=sent))
