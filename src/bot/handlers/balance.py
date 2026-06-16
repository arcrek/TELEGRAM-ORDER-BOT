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
import os
import time
from typing import Optional

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import ContextTypes

from src.bot.states.state_manager import StateManager
from src.bot.utils.language import t
from src.database.connection import get_session_factory
from src.database.models.enums import BalanceTxKind
from src.database.services.balance_service import BalanceService
from src.database.services.bot_user_service import BotUserService
from src.database.services.auto_cancel_service import PAYMENT_EXPIRE_MINUTES
from src.database.services.topup_service import (
    BALANCE_TOPUP_MAX,
    BALANCE_TOPUP_MIN,
    TopupService,
)

logger = logging.getLogger(__name__)

state_manager = StateManager()

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
    topup_message_id: Optional[int],
) -> None:
    """
    Create a PayOS or Pay2S QR for a TopupOrder and send it to the user.
    Updates state and DB with message IDs.
    Called after TopupOrder is created.
    """
    session_factory = get_session_factory()
    session = session_factory()
    try:
        topup_svc = TopupService(session)
        topup = topup_svc.get_by_id(topup_id)
        if not topup:
            logger.error(f"_create_topup_qr: TopupOrder {topup_id} not found")
            return

        # Determine payment provider
        payment_provider = os.getenv("PAYMENT_PROVIDER_DEFAULT", "payos").lower()
        try:
            from config.config import PAYMENT_PROVIDER_DEFAULT as _PPD
            if _PPD:
                payment_provider = str(_PPD).lower()
        except ModuleNotFoundError:
            pass

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

        if payment_provider == "payos":
            try:
                from config.config import (
                    PAYOS_BASE_URL,
                    PAYOS_CLIENT_ID,
                    PAYOS_API_KEY,
                    PAYOS_CHECKSUM_KEY,
                    PAYOS_PARTNER_CODE,
                    PAYOS_RETURN_URL,
                    PAYOS_CANCEL_URL,
                )
            except ModuleNotFoundError:
                PAYOS_BASE_URL = os.getenv("PAYOS_BASE_URL", "https://api-merchant.payos.vn")
                PAYOS_CLIENT_ID = os.getenv("PAYOS_CLIENT_ID", "")
                PAYOS_API_KEY = os.getenv("PAYOS_API_KEY", "")
                PAYOS_CHECKSUM_KEY = os.getenv("PAYOS_CHECKSUM_KEY", "")
                PAYOS_PARTNER_CODE = os.getenv("PAYOS_PARTNER_CODE", "")
                PAYOS_RETURN_URL = os.getenv("PAYOS_RETURN_URL", os.getenv("REDIRECT_URL", "https://t.me/your_bot"))
                PAYOS_CANCEL_URL = os.getenv("PAYOS_CANCEL_URL", os.getenv("REDIRECT_URL", "https://t.me/your_bot"))

            if not PAYOS_CLIENT_ID or not PAYOS_API_KEY or not PAYOS_CHECKSUM_KEY:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ Payment configuration error. Please contact support.",
                )
                return

            from src.payos.client import PayOSClient, PayOSCredentials
            from src.bot.utils.qr import make_qr_png_bytes
            from src.database.services.order_service import OrderService

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
                description = f"{order_prefix}{topup_id}"[:9]
                expired_at = int(time.time()) + PAYMENT_EXPIRE_MINUTES * 60

                try:
                    payos_resp = payos.create_payment_link(
                        order_code=int(payos_order_code),
                        amount=int(amount),
                        description=description,
                        return_url=PAYOS_RETURN_URL,
                        cancel_url=PAYOS_CANCEL_URL,
                        expired_at=expired_at,
                    )
                except Exception as exc:
                    logger.error(f"PayOS create link failed for topup {topup_id}: {exc}", exc_info=True)
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="❌ Payment creation failed. Please try again later.",
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
                    sent = await context.bot.send_photo(
                        chat_id=user_id,
                        photo=qr_image,
                        caption=caption,
                        reply_markup=cancel_keyboard,
                        write_timeout=30,
                        read_timeout=30,
                    )
                    ids_to_track.append(sent.message_id)
                except Exception as exc:
                    logger.error(f"Failed to send PayOS QR for topup: {exc}", exc_info=True)
                    sent = await context.bot.send_message(
                        chat_id=user_id,
                        text=caption,
                        reply_markup=cancel_keyboard,
                    )
                    ids_to_track.append(sent.message_id)
            else:
                sent = await context.bot.send_message(
                    chat_id=user_id,
                    text=caption,
                    reply_markup=cancel_keyboard,
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
            import json as _json
            PAY2S_ENDPOINT = os.getenv("PAY2S_ENDPOINT", "...")
            PARTNER_CODE = os.getenv("PAY2S_PARTNER_CODE", "...")
            ACCESS_KEY = os.getenv("PAY2S_ACCESS_KEY", "...")
            SECRET_KEY = os.getenv("PAY2S_SECRET_KEY", "...")
            _raw_ba = os.getenv("DEFAULT_BANK_ACCOUNTS", "[]")
            try:
                DEFAULT_BANK_ACCOUNTS = _json.loads(_raw_ba)
            except Exception:
                DEFAULT_BANK_ACCOUNTS = []

        if not PAY2S_ENDPOINT or PAY2S_ENDPOINT == "...":
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Payment configuration error. Please contact support.",
            )
            return

        from src.pay2s import create_payment
        import base64
        from io import BytesIO
        from telegram import InputFile

        validated_banks = [
            {"account_number": str(b["account_number"]), "bank_id": str(b["bank_id"]).upper()}
            for b in (DEFAULT_BANK_ACCOUNTS or [])
            if isinstance(b, dict) and "account_number" in b and "bank_id" in b
        ]
        if not validated_banks:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Payment configuration error. Please contact support.",
            )
            return

        ipn_url = os.getenv("IPN_URL", f"http://localhost:{os.getenv('IPN_PORT', '5001')}/ipn")
        redirect_url = os.getenv("REDIRECT_URL", "https://t.me/your_bot")
        order_prefix = os.getenv("ORDER_PREFIX", "MTK")
        order_info = f"{order_prefix}{topup_id}"[:32]
        request_id = str(int(time.time() * 1000))

        payment_response = create_payment(
            endpoint=PAY2S_ENDPOINT,
            access_key=ACCESS_KEY,
            secret_key=SECRET_KEY,
            partner_code=PARTNER_CODE,
            amount=amount,
            order_id=topup_id,
            order_info=order_info,
            redirect_url=redirect_url,
            ipn_url=ipn_url,
            bank_accounts=validated_banks,
            request_id=request_id,
        )

        result_code = payment_response.get("resultCode")
        is_success = (result_code == 0 or result_code == "0") and payment_response.get("payUrl")

        ids_to_track = []
        if topup_message_id:
            ids_to_track.append(topup_message_id)

        if is_success:
            payment_url = payment_response["payUrl"]
            qr_list = payment_response.get("qrList", [])
            qr_code_data = None
            if qr_list:
                qr_code = qr_list[0].get("qrCode", "")
                if qr_code.startswith("data:image/png;base64,"):
                    try:
                        qr_code_data = base64.b64decode(qr_code.replace("data:image/png;base64,", ""))
                    except Exception:
                        qr_code_data = None

            if qr_code_data:
                bank_info = ""
                if qr_list:
                    bank_info = (
                        f"\n\n🏦 Bank: {qr_list[0].get('bank_name', 'N/A')}\n"
                        f"Account: {qr_list[0].get('account_number', 'N/A')}"
                    )
                qr_image = BytesIO(qr_code_data)
                qr_image.name = "qr_code.png"
                sent = await context.bot.send_photo(
                    chat_id=user_id,
                    photo=InputFile(qr_image, filename="qr_code.png"),
                    caption=caption + bank_info,
                    reply_markup=cancel_keyboard,
                )
                ids_to_track.append(sent.message_id)
            else:
                text_msg = caption + f"\n\n🔗 {payment_url}"
                sent = await context.bot.send_message(
                    chat_id=user_id,
                    text=text_msg,
                    reply_markup=cancel_keyboard,
                )
                ids_to_track.append(sent.message_id)
        else:
            error_msg = payment_response.get("message", "Unknown error")
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ Payment creation failed: {error_msg}",
            )
            return

        topup.payment_message_ids = json.dumps(ids_to_track)
        session.commit()
        state_manager.update_user_state(
            user_id,
            topup_payment_message_ids=ids_to_track,
            pending_topup_order_id=topup_id,
        )

    except Exception as exc:
        logger.error(f"Error in _create_topup_qr for {topup_id}: {exc}", exc_info=True)
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
        msg = await update.message.reply_text(text, reply_markup=_balance_view_keyboard(update))
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
        await query.edit_message_text(text, reply_markup=_balance_view_keyboard(update))
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
        await query.edit_message_text("\n".join(lines), reply_markup=back_kb)
    finally:
        session.close()


async def handle_balance_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback: balance_close — delete the balance view message."""
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
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
            except Exception:
                pass

        # Also check state
        user_state = state_manager.get_user_state(user_id)
        if user_state and user_state.topup_payment_message_ids:
            for mid in user_state.topup_payment_message_ids:
                if mid not in msg_ids:
                    msg_ids.append(mid)

        for mid in msg_ids:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=mid)
            except Exception:
                pass

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
