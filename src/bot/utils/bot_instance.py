"""
Utility for sharing bot instance across services.
"""

from telegram import Bot

# Global bot instance that can be accessed by dashboard and other services
_shared_bot_instance: Bot | None = None


def set_shared_bot_instance(bot: Bot) -> None:
    """
    Set the shared bot instance for use by dashboard and other services.
    
    Args:
        bot: Telegram bot instance
    """
    global _shared_bot_instance
    _shared_bot_instance = bot


def get_shared_bot_instance() -> Bot | None:
    """
    Get the shared bot instance.
    
    Returns:
        Bot instance or None if not set
    """
    return _shared_bot_instance

