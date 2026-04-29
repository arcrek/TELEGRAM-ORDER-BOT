"""
Main entry point for the Telegram bot.
"""
import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler
from dotenv import load_dotenv
from src.bot.handlers.commands import (
    start,
    help_command,
    products_command,
    language_command,
    order_history_command,
    handle_products_button,
    unknown_command,
)
from src.bot.handlers.notification_commands import notify_all, notify_user, notify_active
from src.bot.handlers.callbacks import (
    handle_page_navigation,
    handle_product_selection,
    handle_variation_selection,
    handle_quantity_adjustment,
    handle_custom_quantity_prompt,
    handle_custom_quantity_input,
    handle_refresh_product,
    handle_back_to_list,
    handle_payment,
    handle_cancel_order,
    handle_language_selection,
    handle_order_history_page,
    handle_order_detail,
    handle_back_to_order_history,
)
from telegram.ext import CallbackQueryHandler, MessageHandler, filters
from src.ipn import set_global_bot
from src.bot.tasks.auto_cancel_task import AutoCancelTask
from src.bot.utils.bot_instance import set_shared_bot_instance

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def create_bot_application() -> Application:
    """
    Create and configure the Telegram bot application.
    
    Returns:
        Configured Application instance.
    """
    # Get bot token from environment
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
    
    # Create application
    application = Application.builder().token(bot_token).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("products", products_command))
    application.add_handler(CommandHandler("lang", language_command))
    application.add_handler(CommandHandler("language", language_command))
    application.add_handler(CommandHandler("orders", order_history_command))
    
    # Register admin notification commands
    application.add_handler(CommandHandler("notify_all", notify_all))
    application.add_handler(CommandHandler("notify_user", notify_user))
    application.add_handler(CommandHandler("notify_active", notify_active))
    
    # Register callback query handlers
    application.add_handler(CallbackQueryHandler(handle_page_navigation, pattern="^page_"))
    application.add_handler(CallbackQueryHandler(handle_product_selection, pattern="^product_"))
    application.add_handler(CallbackQueryHandler(handle_variation_selection, pattern="^variation_"))
    # Custom quantity handler must be registered BEFORE the general qty_ handler
    application.add_handler(CallbackQueryHandler(handle_custom_quantity_prompt, pattern="^qty_custom_"))
    application.add_handler(CallbackQueryHandler(handle_quantity_adjustment, pattern="^qty_"))
    application.add_handler(CallbackQueryHandler(handle_refresh_product, pattern="^refresh_product$"))
    application.add_handler(CallbackQueryHandler(handle_back_to_list, pattern="^back_to_list$"))
    application.add_handler(CallbackQueryHandler(handle_payment, pattern="^payment_"))
    application.add_handler(CallbackQueryHandler(handle_cancel_order, pattern="^cancel_order_"))
    application.add_handler(CallbackQueryHandler(handle_language_selection, pattern="^lang_"))
    application.add_handler(CallbackQueryHandler(handle_order_history_page, pattern="^order_history"))
    application.add_handler(CallbackQueryHandler(handle_order_detail, pattern="^order_detail_"))
    application.add_handler(CallbackQueryHandler(handle_back_to_order_history, pattern="^back_to_order_history"))
    
    # Register message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_products_button))
    # Custom quantity input handler runs in a separate group so it is not blocked
    # by handle_products_button which matches the same filter.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_quantity_input), group=1)

    # Catch-all for unknown slash commands (including sending just "/")
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    
    return application


def main():
    """Run the bot."""
    logger.info("Starting Telegram bot...")
    
    application = create_bot_application()
    
    # Set global bot instance for IPN processing
    bot = application.bot
    set_global_bot(bot)
    logger.info("Bot instance set for IPN processing")
    
    # Set shared bot instance for dashboard and other services
    set_shared_bot_instance(bot)
    logger.info("Bot instance set for dashboard access")
    
    # Start auto-cancel task
    auto_cancel_task = AutoCancelTask(bot_instance=bot, interval_minutes=5)
    auto_cancel_task.start()
    logger.info("Auto-cancel task started")
    
    try:
        # Start the bot
        logger.info("Bot is running. Press Ctrl+C to stop.")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("Stopping bot...")
        auto_cancel_task.stop()
        logger.info("Bot stopped")


if __name__ == "__main__":
    main()

