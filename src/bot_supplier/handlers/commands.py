"""
Command handlers for the supplier bot.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes
from src.database.connection import get_session_factory
from src.database.services.supplier_service import SupplierService

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command for supplier bot.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    user = update.effective_user
    welcome_message = (
        f"Welcome to Supplier Bot, {user.first_name}! 👋\n\n"
        "This bot helps you manage orders.\n"
        "Use /register to register as a supplier.\n"
        "Use /help to see all available commands."
    )
    await update.message.reply_text(welcome_message)


async def register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /register command for supplier registration.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    user = update.effective_user
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        supplier_service = SupplierService(session)
        
        # Check if already registered
        existing = supplier_service.get_supplier_by_telegram_id(user.id)
        if existing:
            if existing.is_active:
                await update.message.reply_text(
                    f"✅ You are already registered as a supplier!\n\n"
                    f"Supplier ID: {existing.id}\n"
                    f"Name: {existing.name}\n"
                    f"Status: Active"
                )
            else:
                # Reactivate supplier
                supplier_service.update_supplier_status(existing.id, True)
                await update.message.reply_text(
                    f"✅ Your supplier account has been reactivated!\n\n"
                    f"Supplier ID: {existing.id}\n"
                    f"Name: {existing.name}"
                )
            return
        
        # Get supplier name from command arguments or use user's name
        name = " ".join(context.args) if context.args else user.first_name or "Supplier"
        
        # Create supplier
        supplier = supplier_service.create_supplier(
            telegram_user_id=user.id,
            name=name,
            is_active=True,
        )
        
        if supplier:
            await update.message.reply_text(
                f"✅ Successfully registered as supplier!\n\n"
                f"Supplier ID: {supplier.id}\n"
                f"Name: {supplier.name}\n\n"
                f"You will now receive order notifications."
            )
            logger.info(f"Supplier registered: {supplier.id} (Telegram ID: {user.id})")
        else:
            await update.message.reply_text(
                "❌ Registration failed. Please try again or contact support."
            )
            
    except Exception as e:
        logger.error(f"Error during supplier registration: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "❌ An error occurred during registration. Please try again later."
        )
    finally:
        session.close()


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /help command for supplier bot.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    help_text = (
        "📋 Supplier Bot Commands:\n\n"
        "/start - Start the bot\n"
        "/register [name] - Register as a supplier\n"
        "/help - Show this help message\n\n"
        "📦 Order Management:\n"
        "When you receive an order notification, reply to it with the product data.\n"
        "The bot will automatically forward the product to the customer.\n\n"
        "Example reply format:\n"
        "username: user123\n"
        "password: pass456"
    )
    await update.message.reply_text(help_text)

