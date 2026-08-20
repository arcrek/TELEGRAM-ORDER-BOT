"""
Keyboard utility functions for persistent keyboards.
"""
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update

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
    top_buyers_text = t("buttons.top_buyers", update)
    api_text = t("start_menu.api_button", update)
    export_text = t("buttons.export", update)

    keyboard = [
        [KeyboardButton(products_text), KeyboardButton(order_history_text)],
        [KeyboardButton(balance_text), KeyboardButton(top_buyers_text)],
        [KeyboardButton(api_text), KeyboardButton(language_text)],
        [KeyboardButton(export_text)],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )
