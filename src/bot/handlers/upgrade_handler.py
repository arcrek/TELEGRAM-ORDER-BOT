"""
Bot handlers for the UPGRADE delivery flow.

Two paths share a single MessageHandler entrypoint (``handle_upgrade_message``):

1. Customer-reply path (private chat with the bot):
   - Triggered after the IPN processor flips ``Order.awaiting_upgrade_info=True``
     and DMs the customer.
   - The customer's first non-command message is forwarded to every chat in the
     UPGRADE channel (``upgrade_notify_chat_ids``) along with a context header
     and a "Done" inline button. When the upgrade list is empty we fall back to
     the regular ``order_notify_whitelist_chat_ids``. The IDs of the header,
     forwarded message and Done prompt are persisted on
     ``Order.upgrade_forwards`` so the bot can later match an admin's reply or
     Done press back to the originating order.
   - The flag is cleared so subsequent messages no longer match.

2. Admin-reply path (notification chat — group/supergroup):
   - When an admin replies (in either the upgrade channel or the legacy
     whitelist) to either the bot's header or the forwarded customer message,
     the bot copies the admin's content to the customer as an order status
     update, preceded by a header that identifies which order it relates to.
"""
import html as html_module
import json
import logging
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from src.bot.messages.emoji_renderer import render as render_emoji
from src.bot.messages.emoji_renderer import substitute_plain
from src.bot.states.state_manager import shared_state_manager
from src.bot.utils.admin_check import is_admin
from src.bot.utils.language import t
from src.database.connection import get_session_factory
from src.database.models import Order
from src.database.models.enums import DeliveryType, OrderStatus
from src.database.services.app_settings_service import AppSettingsService
from src.database.services.emoji_placeholder_service import EmojiPlaceholderService
from src.database.services.notification_settings_service import (
    NotificationSettingsService,
)
from src.database.services.order_service import OrderService
from src.database.services.user_preference_service import UserPreferenceService
from src.i18n.bot_translations import get_translation
from src.utils.datetime_format import format_local, resolve_tz

logger = logging.getLogger(__name__)

state_manager = shared_state_manager


def _has_upgrade_item(order: Order) -> bool:
    """Return whether an order contains at least one UPGRADE item."""
    return any(
        item.product is not None and item.product.delivery_type == DeliveryType.UPGRADE
        for item in order.items
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def handle_upgrade_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dispatch UPGRADE-related messages to the customer- or admin-reply branch."""
    if update.message is None or update.effective_user is None:
        return

    text = update.message.text or update.message.caption or ""
    if text.startswith("/"):
        return

    chat = update.message.chat
    if chat is None:
        return

    if chat.type == "private":
        await _handle_customer_reply(update, context)
    elif chat.type in ("group", "supergroup", "channel"):
        await _handle_admin_reply(update, context)


# ---------------------------------------------------------------------------
# Customer-reply branch
# ---------------------------------------------------------------------------


async def _handle_customer_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Forward the customer's account-info reply to the notification whitelist.

    Handles two cases:
    1. First reply — order still has awaiting_upgrade_info=True.
    2. Additional reply — customer replies to the original prompt message after
       awaiting_upgrade_info has been cleared. Detected via upgrade_prompt_msg_id.
    """
    user_id = update.effective_user.id

    # Defer to existing state-driven flows (e.g. custom-quantity input).
    user_state = state_manager.get_user_state(user_id)
    if user_state and user_state.waiting_for_custom_quantity:
        return

    session_factory = get_session_factory()
    session = session_factory()

    try:
        order_service = OrderService(session)

        # Case 1: initial reply — order is still awaiting account info.
        order = order_service.get_oldest_awaiting_upgrade_order(user_id)
        is_additional = False

        # Case 2: additional reply — customer explicitly replies to the prompt.
        if not order and update.message.reply_to_message:
            replied_msg_id = update.message.reply_to_message.message_id
            order = order_service.get_order_by_upgrade_prompt_msg_id(user_id, replied_msg_id)
            if order:
                is_additional = True

        if not order:
            return

        product_name = "?"
        variation_name = "?"
        if order.items:
            first_item = order.items[0]
            if first_item.product:
                product_name = first_item.product.name
            if first_item.variation:
                variation_name = first_item.variation.name

        username = update.effective_user.username or "-"
        first_name = update.effective_user.first_name or ""
        last_name = update.effective_user.last_name or ""
        full_name = " ".join(part for part in [first_name, last_name] if part).strip() or "-"

        if is_additional:
            header = get_translation(
                "upgrade.additional_info_header",
                "vi",
                order_id=order.id,
                user_id=user_id,
                username=username,
                name=full_name,
            )
        else:
            header = t(
                "upgrade.forward_header",
                update,
                order_id=order.id,
                user_id=user_id,
                username=username,
                name=full_name,
                product=product_name,
                variation=variation_name,
            )

        notification_service = NotificationSettingsService(session)
        settings = notification_service.get_settings()
        targets = notification_service.get_upgrade_targets(settings)
        if targets:
            logger.info(
                f"UPGRADE info for order {order.id}: routing to upgrade channel ({len(targets)} target(s))"
            )
        else:
            targets = notification_service.get_whitelist_targets(settings)
            if targets:
                logger.info(
                    f"UPGRADE info for order {order.id}: upgrade channel empty, falling back to whitelist ({len(targets)} target(s))"
                )

        # Expand {emo:id} placeholders in the human-facing header (product/variation
        # names may contain them). For the <pre> copy block below, custom emoji can't
        # render in a monospace block, so substitute the plain fallback char instead
        # of leaking the literal token into the admin's tap-to-copy text.
        _emoji_service = EmojiPlaceholderService(session)
        rendered_header, header_parse_mode = render_emoji(header, _emoji_service)
        plain_header = substitute_plain(header, _emoji_service)

        done_button_label = get_translation("upgrade.done_button", "vi")
        done_prompt_text = get_translation("upgrade.done_prompt", "vi", order_id=order.id)

        # Code block copy of the customer's text for easy admin copying.
        customer_text = update.message.text or update.message.caption or ""

        forwards: list[dict] = []
        if not targets:
            logger.warning(
                f"UPGRADE info received for order {order.id} but no upgrade or whitelist targets are configured"
            )
        else:
            for target in targets:
                chat_id = int(target["chat_id"])
                thread_id = target.get("message_thread_id")
                send_kwargs = {"chat_id": chat_id, "text": rendered_header}
                if header_parse_mode is not None:
                    send_kwargs["parse_mode"] = header_parse_mode
                forward_kwargs = {
                    "chat_id": chat_id,
                    "from_chat_id": user_id,
                    "message_id": update.message.message_id,
                }
                done_kwargs = {
                    "chat_id": chat_id,
                    "text": done_prompt_text,
                    "reply_markup": InlineKeyboardMarkup(
                        [[InlineKeyboardButton(
                            done_button_label,
                            callback_data=f"upgrade_done_{order.id}",
                        )]]
                    ),
                }
                if thread_id is not None:
                    send_kwargs["message_thread_id"] = int(thread_id)
                    forward_kwargs["message_thread_id"] = int(thread_id)
                    done_kwargs["message_thread_id"] = int(thread_id)

                try:
                    header_msg = await context.bot.send_message(**send_kwargs)
                    forward_msg = await context.bot.forward_message(**forward_kwargs)

                    # Send a code-block copy of the full notification (header + account
                    # info) so admins can tap-to-copy the entire context in one go.
                    if customer_text:
                        full_content = f"{plain_header}\n{customer_text}"
                        code_kwargs: dict = {
                            "chat_id": chat_id,
                            "text": f"<pre>{html_module.escape(full_content)}</pre>",
                            "parse_mode": "HTML",
                        }
                        if thread_id is not None:
                            code_kwargs["message_thread_id"] = int(thread_id)
                        try:
                            await context.bot.send_message(**code_kwargs)
                        except TelegramError as e:
                            logger.warning(
                                f"Failed to send code-block copy for order {order.id} to {chat_id}: {e}"
                            )

                    # Done prompt is only sent on the first reply, not additional ones.
                    done_msg_id: int | None = None
                    if not is_additional:
                        try:
                            done_msg = await context.bot.send_message(**done_kwargs)
                            done_msg_id = done_msg.message_id
                        except TelegramError:
                            logger.exception(f"Failed to send UPGRADE Done prompt for order {order.id} to {chat_id}")
                    forwards.append(
                        {
                            "chat_id": chat_id,
                            "thread_id": int(thread_id) if thread_id is not None else None,
                            "header_msg_id": header_msg.message_id,
                            "forward_msg_id": forward_msg.message_id,
                            "done_msg_id": done_msg_id,
                        }
                    )
                except TelegramError as e:
                    logger.error(
                        f"Failed to forward UPGRADE info for order {order.id} to {chat_id}: {e}"
                    )

        # Persist the bot's outgoing message IDs so admin replies in the notification
        # chat can be mapped back to this order.
        if forwards:
            existing = _load_forwards(order.upgrade_forwards)
            existing.extend(forwards)
            order.upgrade_forwards = json.dumps(existing)

        # Clear the awaiting flag only on the initial reply.
        if not is_additional:
            order.awaiting_upgrade_info = False
        session.commit()

        try:
            await update.message.reply_text(
                t("upgrade.received", update, order_id=order.id)
            )
        except TelegramError as e:
            logger.error(f"Failed to send UPGRADE confirmation to user {user_id}: {e}")

    # Outermost boundary of the customer-reply forward flow (DB writes +
    # multi-chat Telegram forwarding) — must roll back and log rather than
    # leave the session dirty or crash the handler.
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error in _handle_customer_reply: {e!s}")
        session.rollback()
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Admin-reply branch
# ---------------------------------------------------------------------------


async def _handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Relay an admin's reply (in the notification chat) back to the customer."""
    msg = update.message
    if not msg.reply_to_message:
        return

    chat_id = msg.chat.id
    reply_target_id = msg.reply_to_message.message_id

    session_factory = get_session_factory()
    session = session_factory()

    try:
        # The chat must be in the configured notification whitelist or the
        # UPGRADE channel; otherwise we ignore replies (avoid leaking via
        # random groups the bot was added to).
        notification_service = NotificationSettingsService(session)
        settings = notification_service.get_settings()
        whitelist_targets = notification_service.get_whitelist_targets(settings)
        upgrade_targets = notification_service.get_upgrade_targets(settings)
        allowed_chat_ids = {int(t["chat_id"]) for t in whitelist_targets}
        allowed_chat_ids.update(int(t["chat_id"]) for t in upgrade_targets)
        if chat_id not in allowed_chat_ids:
            return

        order = _find_order_by_forward_message(session, chat_id, reply_target_id)
        if not order:
            return

        # Pick the customer's preferred language for the status-update header.
        try:
            customer_language = UserPreferenceService(session).get_user_language(order.user_id)
        except SQLAlchemyError:
            customer_language = "vi"

        header = get_translation(
            "upgrade.admin_update_header",
            customer_language,
            order_id=order.id,
        )

        try:
            await context.bot.send_message(chat_id=order.user_id, text=header)
            await context.bot.copy_message(
                chat_id=order.user_id,
                from_chat_id=chat_id,
                message_id=msg.message_id,
            )
        except TelegramError as e:
            logger.exception(f"Failed to relay admin update to customer {order.user_id} for order {order.id}")
            try:
                await msg.reply_text(
                    t("upgrade.admin_update_failed", update, order_id=order.id, error=str(e))
                )
            except TelegramError:
                pass
            return

        # Confirm in the notification chat (use the admin's language).
        try:
            await msg.reply_text(t("upgrade.admin_update_sent", update, order_id=order.id))
        except TelegramError as e:
            logger.warning(f"Failed to confirm admin update for order {order.id}: {e}")

    # Same outer boundary as _handle_customer_reply, for the admin-reply path.
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error in _handle_admin_reply: {e!s}")
        session.rollback()
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_forwards(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (TypeError, ValueError):
        return []


def _find_order_by_forward_message(session, chat_id: int, message_id: int) -> Order | None:
    """Return the Order whose stored forward IDs match this reply target."""
    candidates = (
        session.query(Order)
        .filter(Order.upgrade_forwards.isnot(None))
        .order_by(Order.created_at.desc())
        .limit(500)
        .all()
    )
    for order in candidates:
        for entry in _load_forwards(order.upgrade_forwards):
            if int(entry.get("chat_id", 0)) != chat_id:
                continue
            if message_id in (
                int(entry.get("header_msg_id") or 0),
                int(entry.get("forward_msg_id") or 0),
                int(entry.get("done_msg_id") or 0),
            ):
                return order
    return None


# ---------------------------------------------------------------------------
# Admin "Done" callback for the UPGRADE channel
# ---------------------------------------------------------------------------


async def handle_upgrade_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ``upgrade_done_<order_id>`` callbacks.

    Pressed by an admin in the UPGRADE notification channel to mark a
    customer's upgrade order as delivered. Sends a confirmation DM to the
    customer, flips ``Order.status`` to DELIVERED, and clears the inline
    keyboard on the prompt message.
    """
    query = update.callback_query
    if query is None or query.data is None:
        return

    user = query.from_user
    if user is None:
        await query.answer()
        return

    if not is_admin(user.id):
        await query.answer(get_translation("upgrade.not_admin", "vi"), show_alert=True)
        return

    raw = query.data.replace("upgrade_done_", "", 1)
    order_id = raw.strip()
    if not order_id:
        await query.answer()
        return

    session_factory = get_session_factory()
    session = session_factory()

    try:
        order = session.query(Order).filter_by(id=order_id).first()
        if order is None:
            await query.answer(
                get_translation("order.not_found", "vi"),
                show_alert=True,
            )
            return

        # An order can contain more than one item.  The Done prompt is created
        # for an UPGRADE item, so do not reject it merely because another item
        # happens to be first in the relationship collection.
        if not _has_upgrade_item(order):
            await query.answer(
                get_translation("upgrade.not_upgrade_order", "vi"),
                show_alert=True,
            )
            return

        if order.status == OrderStatus.DELIVERED:
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except TelegramError:
                pass
            await query.answer(
                get_translation("upgrade.done_already", "vi"),
                show_alert=True,
            )
            return

        order.status = OrderStatus.DELIVERED
        order.awaiting_upgrade_info = False
        session.commit()

        try:
            customer_language = UserPreferenceService(session).get_user_language(order.user_id)
        except SQLAlchemyError:
            customer_language = "vi"

        try:
            await context.bot.send_message(
                chat_id=order.user_id,
                text=get_translation(
                    "upgrade.done_customer_message",
                    customer_language,
                    order_id=order.id,
                ),
            )
        except TelegramError:
            logger.exception(f"Failed to send UPGRADE done confirmation to customer {order.user_id} for order {order.id}")

        admin_handle = user.username or user.first_name or str(user.id)
        _app_tz = resolve_tz(AppSettingsService(session).get_settings().timezone)
        completed_at = format_local(datetime.now(timezone.utc), _app_tz)
        footer = get_translation(
            "upgrade.done_footer",
            "vi",
            admin=admin_handle,
            time=completed_at,
        )

        try:
            original_text = query.message.text if query.message else ""
            new_text = (original_text or "") + footer
            await query.edit_message_text(new_text, reply_markup=None)
        except TelegramError as e:
            logger.warning(
                f"Failed to update UPGRADE Done prompt for order {order.id}: {e}"
            )
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except TelegramError:
                pass

        await query.answer()

    # Same outer boundary, for the Done-button confirmation path.
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error in handle_upgrade_done: {e!s}")
        session.rollback()
        try:
            await query.answer(
                get_translation("upgrade.admin_update_failed", "vi", order_id=order_id, error=str(e)),
                show_alert=True,
            )
        except TelegramError:
            pass
    finally:
        session.close()
