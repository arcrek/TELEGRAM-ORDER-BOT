"""
Bot utilities package.
"""
from src.bot.utils.admin_check import is_admin, get_admin_telegram_ids
from src.bot.utils.bot_instance import set_shared_bot_instance, get_shared_bot_instance

__all__ = ["is_admin", "get_admin_telegram_ids", "set_shared_bot_instance", "get_shared_bot_instance"]

