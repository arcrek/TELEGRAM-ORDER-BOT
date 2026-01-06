"""
Main entry point for the supplier Telegram bot.
"""
import os
import logging
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv
from src.bot_supplier.handlers.commands import start, register, help_command
from src.bot_supplier.handlers.messages import handle_supplier_reply
from src.pay2s.ipn_order_processor import set_global_supplier_bot

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def create_supplier_bot_application(customer_bot: Bot = None) -> Application:
    """
    Create and configure the supplier Telegram bot application.
    
    Args:
        customer_bot: Optional customer bot instance for forwarding messages
        
    Returns:
        Configured Application instance.
    """
    # Get supplier bot token from environment
    supplier_bot_token = os.getenv("SUPPLIER_TELEGRAM_BOT_TOKEN")
    if not supplier_bot_token:
        raise ValueError("SUPPLIER_TELEGRAM_BOT_TOKEN environment variable is required")
    
    # Create application
    application = Application.builder().token(supplier_bot_token).build()
    
    # Store customer bot in bot_data for message handler
    if customer_bot:
        application.bot_data["customer_bot"] = customer_bot
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("help", help_command))
    
    # Register message handler for replies to order notifications
    # Only handle replies (not all messages)
    application.add_handler(
        MessageHandler(
            filters.REPLY & filters.TEXT & ~filters.COMMAND,
            handle_supplier_reply,
        )
    )
    
    return application


def main(customer_bot: Bot = None):
    """
    Run the supplier bot.
    
    Args:
        customer_bot: Optional customer bot instance for forwarding messages to customers
    """
    logger.info("Starting Supplier Telegram bot...")
    
    application = create_supplier_bot_application(customer_bot=customer_bot)
    
    # Set global supplier bot instance for IPN processing
    supplier_bot = application.bot
    set_global_supplier_bot(supplier_bot)
    logger.info("Supplier bot instance set for IPN processing")
    
    # Start the bot
    logger.info("Supplier bot is running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

