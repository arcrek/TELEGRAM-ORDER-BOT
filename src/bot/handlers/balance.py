"""
Balance (Số dư) wallet handlers for the customer Telegram bot.

Provides:
- handle_balance_button   — text-button entry point (dispatched by handle_products_button)
- handle_balance_view     — callback: balance_view
- handle_balance_topup_start — callback: topup_start
- handle_balance_topup_amount — callback: topup_amount_{value}
- handle_balance_topup_custom — callback: topup_custom
- handle_topup_amount_text — group-1 text handler for custom amount input
- handle_balance_history  — callback: balance_history
- handle_balance_close    — callback: balance_close
- handle_topup_cancel     — callback: cancel_topup_{topup_id}
"""
from __future__ import annotations

import json
import logging
import time

import requests
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from src.bot.messages.emoji_renderer import render as render_emoji
from src.bot.states.state_manager import shared_state_manager
from src.bot.utils.language import t
from src.bot.utils.qr import make_qr_png_bytes
from src.database.connection import get_session_factory
from src.database.models.enums import BalanceTxKind
from src.database.services.app_settings_service import AppSettingsService
from src.database.services.auto_cancel_service import PAYMENT_EXPIRE_MINUTES
from src.database.services.balance_service import BalanceService
from src.database.services.bot_user_service import BotUserService
from src.database.services.emoji_placeholder_service import EmojiPlaceholderService
from src.database.services.order_service import OrderService
from src.database.services.topup_service import (
    BALANCE_TOPUP_MAX,
    BALANCE_TOPUP_MIN,
    TopupService,
)
from src.payos.client import build_payos_client

logger = logging.getLogger(__name__)

state_manager = shared_state_manager

# Preset topup amounts (VND)
TOPUP_PRESETS = [50_000, 100_000, 200_000, 500_000, 1_000_000]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_amount(amount: int) -> str:
    """Format a VND integer with comma thousands separator."""
    return f"{amount:,}"


def _balance_view_keyboard(update: Update) -> InlineKeyboardMarkup:
    topup_btn = InlineKeyboardButton(t("balance.topup_button", update), callback_data="topup_start")
    history_btn = InlineKeyboardButton(t("balance.history_button", update), callback_data="balance_history")
    close_btn = InlineKeyboardButton(t("balance.close_button", update), callback_data="balance_close")
    return InlineKeyboardMarkup([[topup_btn, history_btn], [close_btn]])


def _topup_keyboard(update: Update) -> InlineKeyboardMarkup:
    """Keyboard with preset amounts + custom option."""
    rows = []
    row: list[InlineKeyboardButton] = []
    for amount in TOPUP_PRESETS:
        preset_key = {
            50_000: "balance.preset_50k",
            100_000: "balance.preset_100k",
            200_000: "balance.preset_200k",
            500_000: "balance.preset_500k",
            1_000_000: "balance.preset_1m",
        }[amount]
        label = t(preset_key, update)
        row.append(InlineKeyboardButton(label, callback_data=f"topup_amount_{amount}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(t("balance.preset_custom", update), callback_data="topup_custom")])
    rows.append([InlineKeyboardButton(t("balance.back_button", update), callback_data="balance_view")])
    return InlineKeyboardMarkup(rows)


async def _get_bot_user(session, telegram_user_id: int):
    """Fetch BotUser, tracking the user if they don't exist yet."""
    svc = BotUserService(session)
    return svc.get_user_by_telegram_id(telegram_user_id)


async def _create_topup_qr(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    topup_id: str,
    amount: int,
    user_id: int,
    topup_message_id: int | None,
) -> None:
    """
    Create a PayOS QR for a TopupOrder and send it to the user.
    Updates state and DB with message IDs.
    Called after TopupOrder is created.
    """
    session_factory = get_session_factory()
    session = session_factory()
    try:
        topup_svc = TopupService(session)
        topup = topup_svc.get_by_id(topup_id)
        if not topup:
            logger.exception(f"_create_topup_qr: TopupOrder {topup_id} not found")
            return

        cancel_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                t("balance.topup_cancel_button", update),
                callback_data=f"cancel_topup_{topup_id}",
            )]
        ])
        caption = t(
            "balance.topup_pending_caption",
            update,
            amount=_format_amount(amount),
            topup_id=topup_id,
        )
        rendered_caption, caption_parse_mode = render_emoji(caption, EmojiPlaceholderService(session))

        settings = AppSettingsService(session).get_settings()
        try:
            payos = build_payos_client()
        except RuntimeError as exc:
            logger.error("PayOS configuration error: %s", exc)
            await context.bot.send_message(
                chat_id=user_id,
                text=t("payment.configuration_error", update),
            )
            return

        order_svc = OrderService(session)

        # If a complete payment link already exists, reuse it without calling
        # PayOS again — prevents duplicate links on double-tap.
        if topup.payos_order_code and topup.payos_checkout_url:
            payos_order_code = topup.payos_order_code
            qr_payload = topup.payos_qr_code or topup.payos_checkout_url
            logger.info(f"Reusing existing PayOS link for topup {topup_id} (code={payos_order_code})")
        else:
            if topup.payos_order_code:
                payos_order_code = topup.payos_order_code
            else:
                payos_order_code = order_svc.generate_payos_order_code()
                topup.payment_provider = "payos"
                topup.payos_order_code = payos_order_code
                session.commit()

            description = f"{settings.order_prefix}{topup.id}"[:9]
            expired_at = int(time.time()) + PAYMENT_EXPIRE_MINUTES * 60

            try:
                payos_resp = payos.create_payment_link(
                    order_code=int(payos_order_code),
                    amount=int(amount),
                    description=description,
                    return_url=settings.bot_url,
                    cancel_url=settings.bot_url,
                    expired_at=expired_at,
                )
            except (requests.RequestException, ValueError) as exc:
                logger.error(f"PayOS create link failed for topup {topup_id}: {exc}")
                await context.bot.send_message(
                    chat_id=user_id,
                    text=t("payment.creation_error", update),
                )
                return

            pay_data = (payos_resp or {}).get("data") or {}
            payment_link_id = pay_data.get("paymentLinkId")
            checkout_url = pay_data.get("checkoutUrl")
            qr_code = pay_data.get("qrCode")
            qr_payload = qr_code or checkout_url

            topup.payos_payment_link_id = str(payment_link_id) if payment_link_id else None
            topup.payos_checkout_url = str(checkout_url) if checkout_url else None
            topup.payos_qr_code = str(qr_code) if qr_code else None
            session.commit()

        ids_to_track: list[int] = []
        if topup_message_id:
            ids_to_track.append(topup_message_id)

        if qr_payload:
            try:
                qr_image = make_qr_png_bytes(str(qr_payload))
                logger.info(f"QR image generated: {qr_image.getbuffer().nbytes} bytes for topup {topup_id}")
                sent = await context.bot.send_photo(
                    chat_id=user_id,
                    photo=qr_image,
                    caption=rendered_caption,
                    reply_markup=cancel_keyboard,
                    write_timeout=30,
                    read_timeout=30,
                    parse_mode=caption_parse_mode,
                )
                ids_to_track.append(sent.message_id)
            except Exception:
                logger.exception("Failed to send PayOS QR for topup")
                sent = await context.bot.send_message(
                    chat_id=user_id,
                    text=rendered_caption,
                    reply_markup=cancel_keyboard,
                    parse_mode=caption_parse_mode,
                )
                ids_to_track.append(sent.message_id)
        else:
            sent = await context.bot.send_message(
                chat_id=user_id,
                text=rendered_caption,
                reply_markup=cancel_keyboard,
                parse_mode=caption_parse_mode,
            )
            ids_to_track.append(sent.message_id)

        # Persist message IDs
        topup.payment_message_ids = json.dumps(ids_to_track)
        session.commit()
        state_manager.update_user_state(
            user_id,
            topup_payment_message_ids=ids_to_track,
            pending_topup_order_id=topup_id,
        )
        return

    except Exception:
        logger.exception(f"Error in _create_topup_qr for {topup_id}")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Public handlers
# ---------------------------------------------------------------------------


async def handle_balance_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Entry point from persistent keyboard ('💰 Số dư' / '💰 Balance' button).
    Fetches current balance and shows the balance view as an inline message.
    """
    user = update.effective_user
    if not user:
        return

    session_factory = get_session_factory()
    session = session_factory()
    try:
        bot_user = await _get_bot_user(session, user.id)
        if not bot_user:
            # User must /start first
            await update.message.reply_text(t("errors.not_found", update))
            return

        balance_svc = BalanceService(session)
        balance = balance_svc.get_balance(bot_user.id)

        text = (
            f"{t('balance.view_title', update)}\n\n"
            f"{t('balance.current_balance', update, balance=_format_amount(balance))}"
        )
        rendered, parse_mode = render_emoji(text, EmojiPlaceholderService(session))
        msg = await update.message.reply_text(rendered, reply_markup=_balance_view_keyboard(update), parse_mode=parse_mode)
        state_manager.update_user_state(user.id, balance_message_id=msg.message_id)
    finally:
        session.close()


async def handle_balance_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: balance_view — refresh and show current balance view."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    session_factory = get_session_factory()
    session = session_factory()
    try:
        bot_user = await _get_bot_user(session, user_id)
        if not bot_user:
            await query.edit_message_text(t("errors.not_found", update))
            return

        balance_svc = BalanceService(session)
        balance = balance_svc.get_balance(bot_user.id)

        text = (
            f"{t('balance.view_title', update)}\n\n"
            f"{t('balance.current_balance', update, balance=_format_amount(balance))}"
        )
        rendered, parse_mode = render_emoji(text, EmojiPlaceholderService(session))
        await query.edit_message_text(rendered, reply_markup=_balance_view_keyboard(update), parse_mode=parse_mode)
        state_manager.update_user_state(user_id, balance_message_id=query.message.message_id)
    finally:
        session.close()


async def handle_balance_topup_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: topup_start — show preset amount keyboard."""
    query = update.callback_query
    await query.answer()

    text = t("balance.topup_title", update)
    await query.edit_message_text(text, reply_markup=_topup_keyboard(update))


async def handle_balance_topup_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Callback: topup_amount_{value} — create TopupOrder for a preset amount and
    send the QR payment message.
    """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    raw = query.data.replace("topup_amount_", "")
    try:
        amount = int(raw)
    except ValueError:
        await query.answer("❌ Invalid amount", show_alert=True)
        return

    session_factory = get_session_factory()
    session = session_factory()
    try:
        bot_user = await _get_bot_user(session, user_id)
        if not bot_user:
            await query.edit_message_text(t("errors.not_found", update))
            return

        from src.database.services.block_service import BlockService

        if BlockService(session).is_blocked(
            bot_user.telegram_user_id, query.from_user.username or bot_user.username
        ):
            await query.edit_message_text(t("errors.user_blocked", update))
            return

        topup_svc = TopupService(session)
        try:
            topup = topup_svc.create_topup(bot_user=bot_user, amount=amount)
        except ValueError as exc:
            await query.answer(str(exc), show_alert=True)
            return

        # Edit the current message to a loading placeholder so user sees feedback
        await query.edit_message_text(
            f"⏳ Đang tạo mã thanh toán {_format_amount(amount)} VND..."
        )
        topup_message_id = query.message.message_id

    finally:
        session.close()

    # Now create QR (outside the session above to avoid session conflicts)
    await _create_topup_qr(update, context, topup.id, amount, user_id, topup_message_id)


async def handle_balance_topup_custom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: topup_custom — prompt user to type a custom amount."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    prompt_text = t(
        "balance.topup_amount_prompt",
        update,
        min=_format_amount(BALANCE_TOPUP_MIN),
        max=_format_amount(BALANCE_TOPUP_MAX),
    )
    sent = await query.edit_message_text(
        prompt_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(t("balance.back_button", update), callback_data="topup_start")]
        ]),
    )

    state = state_manager.get_user_state(user_id)
    if state is None:
        from src.bot.states.state_manager import UserState
        state = UserState()

    # Mutual exclusion: clear custom-quantity mode
    state.waiting_for_custom_quantity = False
    state.awaiting_topup_amount = True
    state.topup_message_id = sent.message_id if sent else query.message.message_id
    state_manager.set_user_state(user_id, state)


async def handle_topup_amount_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Group-1 text handler for custom topup amount input.
    Only active when state.awaiting_topup_amount is True.
    """
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    user_state = state_manager.get_user_state(user_id)
    if not user_state or not user_state.awaiting_topup_amount:
        return

    raw = update.message.text.strip().replace(",", "").replace(".", "")
    try:
        amount = int(raw)
    except ValueError:
        await update.message.reply_text(t("balance.topup_amount_not_number", update))
        return

    if amount < BALANCE_TOPUP_MIN or amount > BALANCE_TOPUP_MAX:
        await update.message.reply_text(
            t(
                "balance.topup_amount_invalid",
                update,
                min=_format_amount(BALANCE_TOPUP_MIN),
                max=_format_amount(BALANCE_TOPUP_MAX),
            )
        )
        return

    # Clear the flag only after validation passes
    user_state.awaiting_topup_amount = False
    state_manager.set_user_state(user_id, user_state)

    session_factory = get_session_factory()
    session = session_factory()
    try:
        bot_user = await _get_bot_user(session, user_id)
        if not bot_user:
            await update.message.reply_text(t("errors.not_found", update))
            return

        from src.database.services.block_service import BlockService

        if BlockService(session).is_blocked(
            bot_user.telegram_user_id,
            update.effective_user.username or bot_user.username,
        ):
            await update.message.reply_text(t("errors.user_blocked", update))
            return

        topup_svc = TopupService(session)
        try:
            topup = topup_svc.create_topup(bot_user=bot_user, amount=amount)
        except ValueError as exc:
            await update.message.reply_text(str(exc))
            return
    finally:
        session.close()

    await _create_topup_qr(update, context, topup.id, amount, user_id, topup_message_id=None)


async def handle_balance_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: balance_history — show last 10 balance transactions."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    session_factory = get_session_factory()
    session = session_factory()
    try:
        bot_user = await _get_bot_user(session, user_id)
        if not bot_user:
            await query.edit_message_text(t("errors.not_found", update))
            return

        balance_svc = BalanceService(session)
        balance = balance_svc.get_balance(bot_user.id)
        txns, _ = balance_svc.get_user_history(bot_user.id, page=1, per_page=10)

        lines = [t("balance.history_title", update), ""]
        if not txns:
            lines.append(t("balance.history_empty", update))
        else:
            for txn in txns:
                abs_amount = abs(txn.amount)
                bal_after = txn.balance_after
                date_str = txn.created_at.strftime("%d/%m/%Y %H:%M") if txn.created_at else ""

                if txn.kind == BalanceTxKind.TOPUP:
                    item = t("balance.history_item_topup", update, amount=_format_amount(abs_amount), balance=_format_amount(bal_after))
                elif txn.kind == BalanceTxKind.ORDER_PAYMENT:
                    item = t("balance.history_item_payment", update, amount=_format_amount(abs_amount), balance=_format_amount(bal_after))
                elif txn.kind == BalanceTxKind.ADMIN_ADD:
                    item = t("balance.history_item_admin_add", update, amount=_format_amount(abs_amount), balance=_format_amount(bal_after))
                elif txn.kind == BalanceTxKind.ADMIN_SUBTRACT:
                    item = t("balance.history_item_admin_sub", update, amount=_format_amount(abs_amount), balance=_format_amount(bal_after))
                else:
                    item = t("balance.history_item_admin_set", update, balance=_format_amount(bal_after))

                lines.append(item)
                lines.append(t("balance.history_item_date", update, date=date_str))
                lines.append("")

        lines.append(t("balance.current_balance", update, balance=_format_amount(balance)))

        back_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(t("balance.back_button", update), callback_data="balance_view")]
        ])
        history_text = "\n".join(lines)
        rendered, parse_mode = render_emoji(history_text, EmojiPlaceholderService(session))
        await query.edit_message_text(rendered, reply_markup=back_kb, parse_mode=parse_mode)
    finally:
        session.close()


async def handle_balance_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: balance_close — delete the balance view message."""
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except TelegramError:
        await query.edit_message_reply_markup(reply_markup=None)


async def handle_topup_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: cancel_topup_{topup_id} — cancel a pending topup and delete payment messages."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    topup_id = query.data.replace("cancel_topup_", "")

    session_factory = get_session_factory()
    session = session_factory()
    try:
        topup_svc = TopupService(session)
        topup = topup_svc.get_by_id(topup_id)
        if not topup:
            await query.answer(t("balance.topup_not_found", update), show_alert=True)
            return

        if topup.user_id != user_id:
            await query.answer(t("errors.unauthorized", update), show_alert=True)
            return

        cancelled = topup_svc.cancel_topup(topup_id)
        if not cancelled:
            await query.answer(t("balance.topup_already_paid", update), show_alert=True)
            return

        # Delete payment messages
        msg_ids: list[int] = []
        if topup.payment_message_ids:
            try:
                msg_ids = json.loads(topup.payment_message_ids)
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    "Malformed payment_message_ids for topup %s: %r",
                    topup.id,
                    topup.payment_message_ids,
                )

        # Also check state
        user_state = state_manager.get_user_state(user_id)
        if user_state and user_state.topup_payment_message_ids:
            for mid in user_state.topup_payment_message_ids:
                if mid not in msg_ids:
                    msg_ids.append(mid)

        for mid in msg_ids:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=mid)
            except TelegramError:
                # Expected when Telegram already dropped the message (too old,
                # already deleted, chat cleared) — not worth surfacing above debug.
                logger.debug("Could not delete payment message %s for user %s", mid, user_id)

        # Clear topup state
        state = state_manager.get_user_state(user_id)
        if state:
            state.pending_topup_order_id = None
            state.topup_payment_message_ids = []
            state_manager.set_user_state(user_id, state)

        await context.bot.send_message(
            chat_id=user_id,
            text=t("balance.topup_cancelled", update),
        )
    finally:
        session.close()
