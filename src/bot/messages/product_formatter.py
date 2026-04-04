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

    ITEMS_PER_PAGE = 15
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

    def format_product_list(
        self,
        products: List[Product],
        page: int,
        total_pages: int,
        update: Optional[Update] = None,
        product_choose_text: Optional[str] = None,
    ) -> str:
        """Return product choose text only (no auto title/list/footer)."""
        if product_choose_text and product_choose_text.strip():
            return product_choose_text.strip()
        # Telegram requires non-empty message text.
        return "\u200B"

    def create_product_keyboard(
        self,
        products: List[Product],
        page: int,
        total_pages: int,
        update: Optional[Update] = None,
    ) -> InlineKeyboardMarkup:
        """Create inline keyboard for product selection."""
        keyboard = []
        short_products = []
        long_products = []
        for product in products:
            if self._display_width(product.name) > self._LONG_NAME_ROW_THRESHOLD:
                long_products.append(product)
            else:
                short_products.append(product)

        # Short-name products stay in 3-column layout.
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

        # Long-name products are moved to the bottom and shown one per row.
        for product in long_products:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        product.name,
                        callback_data=f"product_{product.id}",
                    )
                ]
            )

        nav_row = []
        if page > 1:
            prev_text = t('buttons.prev', update) if update else "PREV"
            nav_row.append(InlineKeyboardButton(prev_text, callback_data=f"page_{page - 1}"))
        if page < total_pages:
            next_text = t('buttons.next', update) if update else "NEXT"
            nav_row.append(InlineKeyboardButton(next_text, callback_data=f"page_{page + 1}"))

        if nav_row:
            keyboard.append(nav_row)

        return InlineKeyboardMarkup(keyboard)

    def calculate_total_pages(self, total_items: int, items_per_page: int = None) -> int:
        """Calculate total pages."""
        if items_per_page is None:
            items_per_page = self.ITEMS_PER_PAGE

        if total_items == 0:
            return 1

        return (total_items + items_per_page - 1) // items_per_page
