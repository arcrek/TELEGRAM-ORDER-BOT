"""
Product list formatter for Telegram messages.
"""
import os
from typing import List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from src.database.models import Product
from src.bot.utils.language import t


class ProductFormatter:
    """Formatter for product list messages."""

    ITEMS_PER_PAGE = 15
    _BUTTON_TEXT_MAX_LEN = 40
    _LONG_NAME_ROW_THRESHOLD = 20

    @staticmethod
    def _truncate_button_text(text: str, max_len: int = 40) -> str:
        if len(text) <= max_len:
            return text
        return f"{text[:max_len - 1]}â€¦"

    def format_product_list(
        self,
        products: List[Product],
        page: int,
        total_pages: int,
        update: Optional[Update] = None,
        product_choose_text: Optional[str] = None,
    ) -> str:
        """
        Format product list message with emoji-based design.
        
        Args:
            products: List of Product instances
            page: Current page number
            total_pages: Total number of pages
            update: Telegram update object for translations
        
        Returns:
            Formatted message string
        """
        lines = []
        
        # Product list
        for product in products:
            product_line = f"â€¢ {product.name}"
            lines.append(product_line)

        if product_choose_text and product_choose_text.strip():
            lines.append("")
            lines.append(product_choose_text.strip())
        
        # Footer with support info (read from environment variables)
        support_line_1 = os.getenv("SUPPORT_LINE_1", "ðŸ§‘â€ðŸ’» Há»— trá»£: @muataikhoanpro")
        support_line_2 = os.getenv("SUPPORT_LINE_2", "ðŸ“ž Zalo: 0964935727")
        
        lines.append("")
        if update:
            footer_line_1 = t('products.list.footer_line_1', update, line1=support_line_1)
            footer_line_2 = t('products.list.footer_line_2', update, line2=support_line_2)
        else:
            footer_line_1 = support_line_1
            footer_line_2 = support_line_2
        lines.append(footer_line_1)
        lines.append(footer_line_2)
        
        return "\n".join(lines)

    def create_product_keyboard(
        self,
        products: List[Product],
        page: int,
        total_pages: int,
        update: Optional[Update] = None,
    ) -> InlineKeyboardMarkup:
        """
        Create inline keyboard for product selection.
        
        Args:
            products: List of Product instances
            page: Current page number
            total_pages: Total number of pages
            update: Telegram update object for translations
        
        Returns:
            InlineKeyboardMarkup instance
        """
        keyboard = []
        
        # Product buttons (3 per row)
        row = []
        for product in products:
            button_text = self._truncate_button_text(product.name, self._BUTTON_TEXT_MAX_LEN)
            button = InlineKeyboardButton(
                button_text,
                callback_data=f"product_{product.id}",
            )

            # Long names get their own full-width row for readability.
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
        
        # Add remaining buttons
        if row:
            keyboard.append(row)
        
        # Navigation buttons
        nav_row = []
        if page > 1:
            prev_text = t('buttons.prev', update) if update else "â—€ PREV PAGE"
            nav_row.append(
                InlineKeyboardButton(prev_text, callback_data=f"page_{page - 1}")
            )
        if page < total_pages:
            next_text = t('buttons.next', update) if update else "NEXT PAGE â–¶"
            nav_row.append(
                InlineKeyboardButton(next_text, callback_data=f"page_{page + 1}")
            )
        
        if nav_row:
            keyboard.append(nav_row)
        
        return InlineKeyboardMarkup(keyboard)

    def calculate_total_pages(self, total_items: int, items_per_page: int = None) -> int:
        """
        Calculate total pages.
        
        Args:
            total_items: Total number of items
            items_per_page: Items per page (defaults to ITEMS_PER_PAGE)
        
        Returns:
            Total number of pages
        """
        if items_per_page is None:
            items_per_page = self.ITEMS_PER_PAGE
        
        if total_items == 0:
            return 1
        
        return (total_items + items_per_page - 1) // items_per_page



