"""
Keyboard utility functions for persistent keyboards.
"""
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from src.bot.utils.language import t


def get_persistent_keyboard(update: Update) -> ReplyKeyboardMarkup:
    """
    Get the persistent keyboard with Products, Order History, Balance, and Language buttons.

    Args:
        update: Telegram update object

    Returns:
        ReplyKeyboardMarkup with persistent buttons
    """
    products_text = t("buttons.products", update)
    order_history_text = t("buttons.order_history", update)
    balance_text = t("buttons.balance", update)
    language_text = t("buttons.language", update)

    keyboard = [
        [KeyboardButton(products_text), KeyboardButton(order_history_text)],
        [KeyboardButton(balance_text)],
        [KeyboardButton(language_text)],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )
