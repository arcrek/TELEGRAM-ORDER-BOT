"""
Utility for checking admin permissions in Telegram bot.
"""
import os
from typing import List


def get_admin_telegram_ids() -> List[int]:
    """
    Get list of admin Telegram user IDs from environment variable.
    
    Returns:
        List of admin Telegram user IDs
    """
    admin_ids_str = os.getenv("ADMIN_TELEGRAM_IDS", "")
    if not admin_ids_str:
        return []
    
    try:
        # Support comma-separated list: "123456789,987654321"
        admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]
        return admin_ids
    except ValueError:
        return []


def is_admin(telegram_user_id: int) -> bool:
    """
    Check if a Telegram user ID is an admin.
    
    Args:
        telegram_user_id: Telegram user ID
    
    Returns:
        True if user is admin, False otherwise
    """
    admin_ids = get_admin_telegram_ids()
    return telegram_user_id in admin_ids

