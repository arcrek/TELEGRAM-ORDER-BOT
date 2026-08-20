"""
Main entry point for the Telegram bot.
"""

import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from src.bot.handlers.apitoken import (
    api_command,
    apitoken_command,
    handle_api_create,
    handle_api_menu,
    handle_api_revoke,
)
from src.bot.handlers.balance import (
    handle_balance_close,
    handle_balance_history,
    handle_balance_topup_amount,
    handle_balance_topup_custom,
    handle_balance_topup_start,
    handle_balance_view,
    handle_topup_amount_text,
    handle_topup_cancel,
)
from src.bot.handlers.callbacks import (
    handle_back_to_list,
    handle_back_to_order_history,
    handle_cancel_order,
    handle_custom_quantity_input,
    handle_custom_quantity_prompt,
    handle_language_selection,
    handle_order_detail,
    handle_order_history_page,
    handle_page_navigation,
    handle_pay_with_balance,
    handle_pay_with_qr,
    handle_payment,
    handle_product_selection,
    handle_quantity_adjustment,
    handle_refresh_product,
    handle_show_products_list,
    handle_variation_selection,
)
from src.bot.handlers.commands import (
    balance_command,
    block_command,
    doanhthu_command,
    handle_products_button,
    handle_start_history,
    handle_start_menu,
    handle_start_products,
    handle_top_buyers_button,
    help_command,
    language_command,
    order_history_command,
    products_command,
    setadmin_command,
    start,
    unblock_command,
    unknown_command,
)
from src.bot.handlers.emoji_admin import handle_emoji_capture, set_emo_command
from src.bot.handlers.export import (
    export_command,
    handle_export_back,
    handle_export_cancel,
    handle_export_generate,
    handle_export_product,
    handle_export_start,
    handle_export_variant_toggle,
)
from src.bot.handlers.manual import handle_manual_list, handle_manual_view
from src.bot.handlers.notification_commands import (
    notify_active,
    notify_all,
    notify_user,
)
from src.bot.handlers.refund import (
    handle_refund_cancel,
    handle_refund_credit,
    refund_command,
)
from src.bot.handlers.upgrade_handler import handle_upgrade_done, handle_upgrade_message
from src.bot.tasks.auto_cancel_task import AutoCancelTask
from src.bot.utils.bot_instance import set_shared_bot_instance
from src.ipn import set_global_bot

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
    application.add_handler(CommandHandler("block", block_command))
    application.add_handler(CommandHandler("unblock", unblock_command))
    application.add_handler(CommandHandler("set_emo", set_emo_command))
    application.add_handler(CommandHandler("top", handle_top_buyers_button))
    application.add_handler(CommandHandler("doanhthu", doanhthu_command))
    application.add_handler(CommandHandler("api", api_command))
    application.add_handler(CommandHandler("apitoken", apitoken_command))
    application.add_handler(CommandHandler("rf", refund_command))
    application.add_handler(CommandHandler("export", export_command))

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
        CallbackQueryHandler(handle_manual_list, pattern="^manual_list_")
    )
    application.add_handler(
        CallbackQueryHandler(handle_manual_view, pattern="^manual_view_")
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

    # /export flow callbacks
    application.add_handler(
        CallbackQueryHandler(handle_export_start, pattern="^start_export$")
    )
    application.add_handler(
        CallbackQueryHandler(handle_export_product, pattern="^export_prod_")
    )
    application.add_handler(
        CallbackQueryHandler(handle_export_variant_toggle, pattern="^export_var_")
    )
    application.add_handler(
        CallbackQueryHandler(handle_export_generate, pattern="^export_go$")
    )
    application.add_handler(
        CallbackQueryHandler(handle_export_back, pattern="^export_back$")
    )
    application.add_handler(
        CallbackQueryHandler(handle_export_cancel, pattern="^export_cancel$")
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

    # Prorated refund callbacks (/rf command)
    application.add_handler(
        CallbackQueryHandler(handle_refund_credit, pattern="^rf_credit_")
    )
    application.add_handler(
        CallbackQueryHandler(handle_refund_cancel, pattern="^rf_cancel_")
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
    # Emoji capture: only acts when the user is in /set_emo awaiting state.
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_emoji_capture),
        group=4,
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
