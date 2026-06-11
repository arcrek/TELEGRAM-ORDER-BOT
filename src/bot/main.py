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
    setadmin_command,
    balance_command,
    unknown_command,
    handle_top_buyers_button,
    doanhthu_command,
    handle_start_menu,
    handle_start_products,
    handle_start_history,
)
from src.bot.handlers.notification_commands import (
    notify_all,
    notify_user,
    notify_active,
)
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
    handle_show_products_list,
    handle_pay_with_qr,
    handle_pay_with_balance,
)
from src.bot.handlers.balance import (
    handle_balance_view,
    handle_balance_topup_start,
    handle_balance_topup_amount,
    handle_balance_topup_custom,
    handle_topup_amount_text,
    handle_balance_history,
    handle_balance_close,
    handle_topup_cancel,
)
from src.bot.handlers.upgrade_handler import handle_upgrade_done, handle_upgrade_message
from src.bot.handlers.apitoken import (
    apitoken_command,
    handle_api_menu,
    handle_api_create,
    handle_api_revoke,
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
    application.add_handler(CommandHandler("history", order_history_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("sodu", balance_command))
    application.add_handler(CommandHandler("setadmin", setadmin_command))
    application.add_handler(CommandHandler("top", handle_top_buyers_button))
    application.add_handler(CommandHandler("doanhthu", doanhthu_command))
    application.add_handler(CommandHandler("apitoken", apitoken_command))

    # Register admin notification commands
    application.add_handler(CommandHandler("notify_all", notify_all))
    application.add_handler(CommandHandler("notify_user", notify_user))
    application.add_handler(CommandHandler("notify_active", notify_active))

    # Register callback query handlers
    application.add_handler(
        CallbackQueryHandler(handle_page_navigation, pattern="^page_")
    )
    application.add_handler(
        CallbackQueryHandler(handle_product_selection, pattern="^product_")
    )
    application.add_handler(
        CallbackQueryHandler(handle_variation_selection, pattern="^variation_")
    )
    # Custom quantity handler must be registered BEFORE the general qty_ handler
    application.add_handler(
        CallbackQueryHandler(handle_custom_quantity_prompt, pattern="^qty_custom_")
    )
    application.add_handler(
        CallbackQueryHandler(handle_quantity_adjustment, pattern="^qty_")
    )
    application.add_handler(
        CallbackQueryHandler(handle_refresh_product, pattern="^refresh_product$")
    )
    application.add_handler(
        CallbackQueryHandler(handle_back_to_list, pattern="^back_to_list$")
    )
    application.add_handler(CallbackQueryHandler(handle_payment, pattern="^payment_"))
    application.add_handler(
        CallbackQueryHandler(handle_cancel_order, pattern="^cancel_order_")
    )
    application.add_handler(
        CallbackQueryHandler(handle_language_selection, pattern="^lang_")
    )
    application.add_handler(
        CallbackQueryHandler(handle_order_history_page, pattern="^order_history")
    )
    application.add_handler(
        CallbackQueryHandler(handle_order_detail, pattern="^order_detail_")
    )
    application.add_handler(
        CallbackQueryHandler(
            handle_back_to_order_history, pattern="^back_to_order_history"
        )
    )
    application.add_handler(
        CallbackQueryHandler(handle_upgrade_done, pattern="^upgrade_done_")
    )
    application.add_handler(
        CallbackQueryHandler(handle_show_products_list, pattern="^show_products_list$")
    )

    # Start menu callbacks
    application.add_handler(
        CallbackQueryHandler(handle_start_products, pattern="^start_products$")
    )
    application.add_handler(
        CallbackQueryHandler(handle_start_history, pattern="^start_history$")
    )
    application.add_handler(
        CallbackQueryHandler(handle_start_menu, pattern="^start_menu$")
    )
    # API management callbacks
    application.add_handler(
        CallbackQueryHandler(handle_api_menu, pattern="^start_api$")
    )
    application.add_handler(
        CallbackQueryHandler(handle_api_create, pattern="^api_create$")
    )
    application.add_handler(
        CallbackQueryHandler(handle_api_revoke, pattern="^api_revoke$")
    )

    # Balance / topup callback handlers
    application.add_handler(
        CallbackQueryHandler(handle_balance_view, pattern="^balance_view$")
    )
    application.add_handler(
        CallbackQueryHandler(handle_balance_topup_start, pattern="^topup_start$")
    )
    application.add_handler(
        CallbackQueryHandler(handle_balance_topup_amount, pattern="^topup_amount_")
    )
    application.add_handler(
        CallbackQueryHandler(handle_balance_topup_custom, pattern="^topup_custom$")
    )
    application.add_handler(
        CallbackQueryHandler(handle_balance_history, pattern="^balance_history$")
    )
    application.add_handler(
        CallbackQueryHandler(handle_balance_close, pattern="^balance_close$")
    )
    application.add_handler(
        CallbackQueryHandler(handle_topup_cancel, pattern="^cancel_topup_")
    )
    # Payment method picker callbacks
    application.add_handler(
        CallbackQueryHandler(handle_pay_with_balance, pattern="^pay_balance_")
    )
    application.add_handler(
        CallbackQueryHandler(handle_pay_with_qr, pattern="^pay_qr_")
    )

    # Register message handlers
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_products_button)
    )
    # Custom quantity input handler runs in a separate group so it is not blocked
    # by handle_products_button which matches the same filter.
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_quantity_input),
        group=1,
    )
    # Custom topup amount input — own group so it is not shadowed by the
    # custom-quantity handler in group=1 (PTB runs only one matching handler
    # per group; identical TEXT filters mean only the first registered one
    # ever fires). Gates internally on awaiting_topup_amount flag.
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topup_amount_text),
        group=3,
    )
    # UPGRADE-delivery dispatcher: handles both the customer's account-info reply
    # (private chat) and admin status-update replies (notification chat).
    # Matches any non-command message so we can carry text/photo/document.
    application.add_handler(
        MessageHandler(~filters.COMMAND, handle_upgrade_message), group=2
    )

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

    # Start auto-cancel task once the bot's event loop is running, so the task
    # can schedule notification coroutines onto that loop (not a throwaway one).
    auto_cancel_task = AutoCancelTask(bot_instance=bot, interval_minutes=5)

    async def _start_auto_cancel(_application) -> None:
        import asyncio
        auto_cancel_task.main_loop = asyncio.get_running_loop()
        auto_cancel_task.start()
        logger.info("Auto-cancel task started (bound to bot event loop)")

    application.post_init = _start_auto_cancel

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
