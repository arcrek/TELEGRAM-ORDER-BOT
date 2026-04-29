"""
Bot handlers for the UPGRADE delivery flow.

Two paths share a single MessageHandler entrypoint (``handle_upgrade_message``):

1. Customer-reply path (private chat with the bot):
   - Triggered after the IPN processor flips ``Order.awaiting_upgrade_info=True``
     and DMs the customer.
   - The customer's first non-command message is forwarded to every chat in the
     notification whitelist along with a context header. The IDs of both the
     header and the forwarded message are persisted on
     ``Order.upgrade_forwards`` so the bot can later match an admin's reply
     back to the originating order.
   - The flag is cleared so subsequent messages no longer match.

2. Admin-reply path (notification chat — group/supergroup):
   - When an admin replies (in the notification chat) to either the bot's
     header or the forwarded customer message, the bot copies the admin's
     content to the customer as an order status update, preceded by a header
     that identifies which order it relates to.
"""
import json
import logging
from typing import Optional

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from src.bot.states.state_manager import StateManager
from src.bot.utils.language import t
from src.database.connection import get_session_factory
from src.database.models import Order
from src.database.services.notification_settings_service import NotificationSettingsService
from src.database.services.order_service import OrderService
from src.database.services.user_preference_service import UserPreferenceService
from src.i18n.bot_translations import get_translation

logger = logging.getLogger(__name__)

state_manager = StateManager()


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
    """Forward the customer's account-info reply to the notification whitelist."""
    user_id = update.effective_user.id

    # Defer to existing state-driven flows (e.g. custom-quantity input).
    user_state = state_manager.get_user_state(user_id)
    if user_state and user_state.waiting_for_custom_quantity:
        return

    session_factory = get_session_factory()
    session = session_factory()

    try:
        order_service = OrderService(session)
        order = order_service.get_oldest_awaiting_upgrade_order(user_id)
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
        targets = notification_service.get_whitelist_targets(settings)

        forwards: list[dict] = []
        if not targets:
            logger.warning(
                f"UPGRADE info received for order {order.id} but notification whitelist is empty"
            )
        else:
            for target in targets:
                chat_id = int(target["chat_id"])
                thread_id = target.get("message_thread_id")
                send_kwargs = {"chat_id": chat_id, "text": header}
                forward_kwargs = {
                    "chat_id": chat_id,
                    "from_chat_id": user_id,
                    "message_id": update.message.message_id,
                }
                if thread_id is not None:
                    send_kwargs["message_thread_id"] = int(thread_id)
                    forward_kwargs["message_thread_id"] = int(thread_id)

                try:
                    header_msg = await context.bot.send_message(**send_kwargs)
                    forward_msg = await context.bot.forward_message(**forward_kwargs)
                    forwards.append(
                        {
                            "chat_id": chat_id,
                            "thread_id": int(thread_id) if thread_id is not None else None,
                            "header_msg_id": header_msg.message_id,
                            "forward_msg_id": forward_msg.message_id,
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

        order.awaiting_upgrade_info = False
        session.commit()

        try:
            await update.message.reply_text(
                t("upgrade.received", update, order_id=order.id)
            )
        except TelegramError as e:
            logger.error(f"Failed to send UPGRADE confirmation to user {user_id}: {e}")

    except Exception as e:
        logger.error(f"Error in _handle_customer_reply: {str(e)}", exc_info=True)
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
        # The chat must be in the configured notification whitelist; otherwise we
        # ignore replies (avoid leaking via random groups the bot was added to).
        notification_service = NotificationSettingsService(session)
        targets = notification_service.get_whitelist_targets()
        whitelisted_chat_ids = {int(t["chat_id"]) for t in targets}
        if chat_id not in whitelisted_chat_ids:
            return

        order = _find_order_by_forward_message(session, chat_id, reply_target_id)
        if not order:
            return

        # Pick the customer's preferred language for the status-update header.
        try:
            customer_language = UserPreferenceService(session).get_user_language(order.user_id)
        except Exception:
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
            logger.error(
                f"Failed to relay admin update to customer {order.user_id} for order {order.id}: {e}"
            )
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

    except Exception as e:
        logger.error(f"Error in _handle_admin_reply: {str(e)}", exc_info=True)
        session.rollback()
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_forwards(raw: Optional[str]) -> list[dict]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (TypeError, ValueError):
        return []


def _find_order_by_forward_message(session, chat_id: int, message_id: int) -> Optional[Order]:
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
            ):
                return order
    return None
