"""
Product list formatter for Telegram messages.
"""
from typing import List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from src.database.models import Product
from src.bot.utils.language import t


class ProductFormatter:
    """Formatter for product list messages."""

    ITEMS_PER_PAGE = 15
    _LONG_NAME_ROW_THRESHOLD = 20

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

        # Product buttons (3 per row for short labels).
        row = []
        for product in products:
            button_text = product.name
            button = InlineKeyboardButton(
                button_text,
                callback_data=f"product_{product.id}",
            )

            # Long names get their own row.
            if len(button_text) > self._LONG_NAME_ROW_THRESHOLD:
                if row:
                    keyboard.append(row)
                    row = []
                keyboard.append([button])
            else:
                row.append(button)
                if len(row) == 3:
                    keyboard.append(row)
                    row = []

        if row:
            keyboard.append(row)

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
