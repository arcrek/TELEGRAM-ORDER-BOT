"""
Product list formatter for Telegram messages.
"""
import unicodedata
from typing import List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from src.database.models import Product
from src.bot.utils.language import t


class ProductFormatter:
    """Formatter for product list messages."""

    _LONG_NAME_ROW_THRESHOLD = 18

    @staticmethod
    def _display_width(text: str) -> int:
        """
        Approximate display width for Telegram buttons.
        Wide unicode chars count as 2 cells.
        """
        width = 0
        for ch in text:
            width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        return width

    def format_product_list(self, product_choose_text: Optional[str] = None) -> str:
        """Return product choose text only."""
        if product_choose_text and product_choose_text.strip():
            return product_choose_text.strip()
        # Telegram requires non-empty message text.
        return "​"

    def create_product_keyboard(
        self,
        products: List[Product],
        update: Optional[Update] = None,
    ) -> InlineKeyboardMarkup:
        """Create inline keyboard for product selection with order history button at bottom."""
        keyboard = []
        short_products = []
        long_products = []
        for product in products:
            if self._display_width(product.name) > self._LONG_NAME_ROW_THRESHOLD:
                long_products.append(product)
            else:
                short_products.append(product)

        # Short-name products in 3-column layout.
        row = []
        for product in short_products:
            row.append(
                InlineKeyboardButton(
                    product.name,
                    callback_data=f"product_{product.id}",
                )
            )
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        # Long-name products one per row.
        for product in long_products:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        product.name,
                        callback_data=f"product_{product.id}",
                    )
                ]
            )

        order_history_text = t('buttons.order_history', update) if update else "📋 Order History"
        keyboard.append([InlineKeyboardButton(order_history_text, callback_data="order_history")])

        return InlineKeyboardMarkup(keyboard)
