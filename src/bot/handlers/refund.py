"""
Admin-only /rf command — prorated refund for a paid order.

Usage: /rf <order_id> <duration>
  duration examples: 30, 30d, 4w, 1m, 2months, 1y

All user-facing strings are hardcoded Vietnamese (admin command; explicit
decision to diverge from i18n for admin-only flows).
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.bot.utils.admin_check import is_admin
from src.database.connection import get_session_factory
from src.database.models.enums import OrderStatus
from src.database.services.app_settings_service import AppSettingsService
from src.database.services.balance_service import BalanceService
from src.database.services.bot_user_service import BotUserService
from src.database.services.order_service import OrderService
from src.utils.datetime_format import format_local, resolve_tz
from src.utils.refund_calc import compute_refund as _compute_refund
from src.utils.refund_calc import parse_duration_to_days

logger = logging.getLogger(__name__)

# Statuses eligible for a refund.
_ELIGIBLE = {OrderStatus.PAID, OrderStatus.PROCESSING, OrderStatus.DELIVERED}


async def refund_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/rf <order_id> <duration> — show prorated refund breakdown (admin only)."""
    if not update.message:
        return

    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("⛔ Chỉ admin mới dùng được lệnh này.")
        return

    args = context.args or []
    if len(args) != 2:
        await update.message.reply_text(
            "❌ Sai cú pháp. Dùng: /rf <order_id> <thời_hạn>\n\n"
            "Ví dụ:\n"
            "  /rf abc12345 30d\n"
            "  /rf abc12345 1m\n"
            "  /rf abc12345 1y"
        )
        return

    order_id = args[0]
    duration_days = parse_duration_to_days(args[1])
    if duration_days is None:
        await update.message.reply_text(
            "❌ Thời hạn không hợp lệ.\nVí dụ hợp lệ: 30, 30d, 4w, 1m, 2months, 1y"
        )
        return

    session_factory = get_session_factory()
    session = session_factory()
    try:
        order_service = OrderService(session)
        order = order_service.get_order_by_id(order_id)
        if order is None:
            await update.message.reply_text(f"❌ Không tìm thấy đơn hàng: {order_id}")
            return

        if order.status not in _ELIGIBLE:
            await update.message.reply_text(
                f"❌ Đơn hàng {order_id} không đủ điều kiện hoàn tiền.\n"
                f"Trạng thái hiện tại: {order.status.value}\n"
                f"Chỉ hoàn tiền khi đơn ở trạng thái: paid, processing, delivered."
            )
            return

        # Load buyer display name.
        bot_user_service = BotUserService(session)
        bot_user = bot_user_service.get_user_by_telegram_id(order.user_id)
        if bot_user:
            buyer_name = bot_user.first_name or ""
            buyer_username = f"@{bot_user.username}" if bot_user.username else ""
            buyer_display = f"{buyer_name} {buyer_username}".strip() or str(
                order.user_id
            )
        else:
            buyer_display = str(order.user_id)

        # Compute refund.
        elapsed, remaining, refund_amount = _compute_refund(
            order.total_amount, duration_days, order.created_at
        )
        daily_rate = round(order.total_amount / duration_days)

        # Format buy date in app timezone.
        app_settings_svc = AppSettingsService(session)
        app_tz = resolve_tz(app_settings_svc.get_settings().timezone)
        buy_date_str = format_local(order.created_at, app_tz, "%d/%m/%Y %H:%M %Z")

        total_fmt = f"{order.total_amount:,}".replace(",", ".")
        daily_fmt = f"{daily_rate:,}".replace(",", ".")
        refund_fmt = f"{refund_amount:,}".replace(",", ".")

        lines = [
            "💸 HOÀN TIỀN ĐƠN HÀNG",
            "",
            f"📋 Mã đơn: {order_id}",
            f"👤 Người mua: {buyer_display}",
            f"💰 Tổng tiền: {total_fmt} VND",
            "",
            f"📅 Ngày mua: {buy_date_str}",
            f"⏳ Thời hạn: {duration_days} ngày",
            f"📆 Đã dùng: {elapsed} ngày",
            f"⌛ Còn lại: {remaining} ngày",
            f"📊 Giá/ngày: {daily_fmt} VND",
            "",
        ]

        if refund_amount > 0:
            lines.append(f"✅ Số tiền hoàn: {refund_fmt} VND")
            text = "\n".join(lines)
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ Hoàn vào số dư",
                            callback_data=f"rf_credit_{order_id}_{duration_days}",
                        ),
                        InlineKeyboardButton(
                            "❌ Huỷ",
                            callback_data=f"rf_cancel_{order_id}",
                        ),
                    ]
                ]
            )
            await update.message.reply_text(text, reply_markup=keyboard)
        else:
            lines.append("ℹ️ Không có số tiền hoàn (đã hết hạn).")
            text = "\n".join(lines)
            await update.message.reply_text(text)

    except Exception as e:
        logger.exception("Error in refund_command")
        await update.message.reply_text(f"❌ Lỗi: {e}")
    finally:
        session.close()


async def handle_refund_credit(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Callback: admin confirms refund — atomically mark order REFUNDED and credit balance."""
    query = update.callback_query
    if not query:
        return

    await query.answer()

    user = update.effective_user
    if not user or not is_admin(user.id):
        await query.edit_message_text("⛔ Chỉ admin mới dùng được lệnh này.")
        return

    # Callback data format: rf_credit_<order_id>_<duration_days>
    # order_id is 8-hex (no underscore), duration_days is an integer.
    data = query.data or ""
    # Strip prefix, then rsplit so we peel off duration_days from the right.
    payload = data[len("rf_credit_") :]
    try:
        order_id, duration_str = payload.rsplit("_", 1)
        duration_days = int(duration_str)
    except (ValueError, AttributeError):
        await query.edit_message_text("❌ Dữ liệu callback không hợp lệ.")
        return

    session_factory = get_session_factory()
    session = session_factory()
    try:
        order_service = OrderService(session)
        order = order_service.get_order_by_id(order_id)
        if order is None:
            await query.edit_message_text(f"❌ Không tìm thấy đơn hàng: {order_id}")
            return

        # Recompute with fresh elapsed days (may cross a day boundary).
        elapsed, _remaining, refund_amount = _compute_refund(
            order.total_amount, duration_days, order.created_at
        )

        if refund_amount <= 0:
            await query.edit_message_text(
                f"ℹ️ Đơn {order_id}: không có số tiền hoàn (đã hết hạn, "
                f"elapsed={elapsed}d >= duration={duration_days}d). Không thực hiện hoàn tiền."
            )
            return

        balance_service = BalanceService(session)
        success, reason = balance_service.refund_order(order_id, refund_amount, user.id)

        if success:
            # Read the new balance to display it.
            from sqlalchemy import select

            from src.database.models import BotUser

            bot_user = session.execute(
                select(BotUser).where(BotUser.telegram_user_id == order.user_id)
            ).scalar_one_or_none()
            new_balance = bot_user.balance if bot_user else 0
            refund_fmt = f"{refund_amount:,}".replace(",", ".")
            balance_fmt = f"{new_balance:,}".replace(",", ".")
            await query.edit_message_text(
                f"✅ Đã hoàn tiền thành công!\n\n"
                f"📋 Mã đơn: {order_id}\n"
                f"💰 Số tiền hoàn: {refund_fmt} VND\n"
                f"💳 Số dư mới của người dùng: {balance_fmt} VND"
            )
        elif reason == "ineligible":
            await query.edit_message_text(
                f"❌ Đơn {order_id} đã được hoàn tiền hoặc không đủ điều kiện."
            )
        elif reason == "user_not_found":
            await query.edit_message_text(
                f"❌ Không tìm thấy tài khoản người dùng cho đơn {order_id}."
            )
        else:
            await query.edit_message_text(
                f"❌ Không thể hoàn tiền đơn {order_id}: {reason}"
            )

    except Exception as e:
        logger.exception("Error in handle_refund_credit")
        await query.edit_message_text(f"❌ Lỗi khi hoàn tiền: {e}")
    finally:
        session.close()


async def handle_refund_cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Callback: admin cancels the refund — no DB change."""
    query = update.callback_query
    if not query:
        return

    await query.answer()
    await query.edit_message_text("Đã huỷ hoàn tiền.")
