"""
Notification command handlers for admin users.
"""
import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.bot.utils.admin_check import is_admin
from src.database.connection import get_session_factory
from src.database.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


async def notify_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /notify_all command - send notification to all users who pressed /start.
    Admin only.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    user_id = update.effective_user.id
    
    # Check admin permission
    if not is_admin(user_id):
        await update.message.reply_text("❌ This command is only available to administrators.")
        return
    
    # Get message from command arguments
    if not context.args:
        await update.message.reply_text(
            "Usage: /notify_all <message>\n\n"
            "Example: /notify_all Hello everyone! This is a broadcast message."
        )
        return
    
    message = " ".join(context.args)
    
    # Send notification
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        notification_service = NotificationService(session, bot=context.bot)
        results = notification_service.send_notification_to_all_started(message)
        
        # Report results
        report = (
            f"✅ Notification sent!\n\n"
            f"📊 Statistics:\n"
            f"• Total users: {results['total']}\n"
            f"• Successful: {results['success']}\n"
            f"• Failed: {results['failed']}"
        )
        await update.message.reply_text(report)
        
    except Exception as e:
        logger.exception(f"Error sending notification: {e!s}")
        await update.message.reply_text(f"❌ Error sending notification: {e!s}")
    finally:
        session.close()


async def notify_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /notify_user command - send notification to specific user.
    Admin only.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    user_id = update.effective_user.id
    
    # Check admin permission
    if not is_admin(user_id):
        await update.message.reply_text("❌ This command is only available to administrators.")
        return
    
    # Get user ID and message from command arguments
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /notify_user <telegram_user_id> <message>\n\n"
            "Example: /notify_user 123456789 Hello! This is a personal message."
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        message = " ".join(context.args[1:])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Please provide a valid Telegram user ID.")
        return
    
    # Send notification
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        notification_service = NotificationService(session, bot=context.bot)
        result = notification_service.send_notification_to_user(target_user_id, message)
        
        if result["success"]:
            await update.message.reply_text(
                f"✅ Notification sent successfully to user {target_user_id}!"
            )
        else:
            error_msg = result.get("error", "Unknown error")
            await update.message.reply_text(
                f"❌ Failed to send notification to user {target_user_id}.\n"
                f"Error: {error_msg}"
            )
        
    except Exception as e:
        logger.exception(f"Error sending notification: {e!s}")
        await update.message.reply_text(f"❌ Error sending notification: {e!s}")
    finally:
        session.close()


async def notify_active(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /notify_active command - send notification to active users only.
    Admin only.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    user_id = update.effective_user.id
    
    # Check admin permission
    if not is_admin(user_id):
        await update.message.reply_text("❌ This command is only available to administrators.")
        return
    
    # Get message from command arguments
    if not context.args:
        await update.message.reply_text(
            "Usage: /notify_active <message>\n\n"
            "Example: /notify_active Hello active users! This message is for you."
        )
        return
    
    message = " ".join(context.args)
    
    # Send notification
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        notification_service = NotificationService(session, bot=context.bot)
        results = notification_service.send_notification_to_active_users(message)
        
        # Report results
        report = (
            f"✅ Notification sent to active users!\n\n"
            f"📊 Statistics:\n"
            f"• Total active users: {results['total']}\n"
            f"• Successful: {results['success']}\n"
            f"• Failed: {results['failed']}"
        )
        await update.message.reply_text(report)
        
    except Exception as e:
        logger.exception(f"Error sending notification: {e!s}")
        await update.message.reply_text(f"❌ Error sending notification: {e!s}")
    finally:
        session.close()

