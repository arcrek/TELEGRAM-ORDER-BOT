"""
Bot utilities package.
"""
from src.bot.utils.admin_check import get_admin_telegram_ids, is_admin
from src.bot.utils.bot_instance import get_shared_bot_instance, set_shared_bot_instance

__all__ = ["get_admin_telegram_ids", "get_shared_bot_instance", "is_admin", "set_shared_bot_instance"]

