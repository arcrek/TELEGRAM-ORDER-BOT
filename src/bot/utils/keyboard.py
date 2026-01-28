"""
Keyboard utility functions for persistent keyboards.
"""
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from src.bot.utils.language import get_user_language, t


def get_persistent_keyboard(update: Update) -> ReplyKeyboardMarkup:
    """
    Get the persistent keyboard with Products button.
    
    Args:
        update: Telegram update object
        
    Returns:
        ReplyKeyboardMarkup with persistent buttons
    """
    products_text = t('buttons.products', update)
    
    keyboard = [
        [KeyboardButton(products_text)]
    ]
    
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )
