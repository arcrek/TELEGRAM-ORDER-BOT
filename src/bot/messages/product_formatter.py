"""
Product list formatter for Telegram messages.
"""
from typing import List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from src.database.models import Product
from src.bot.utils.language import t
from config.config import SUPPORT_LINE_1, SUPPORT_LINE_2


class ProductFormatter:
    """Formatter for product list messages."""

    ITEMS_PER_PAGE = 15

    def format_product_list(
        self,
        products: List[Product],
        page: int,
        total_pages: int,
        update: Optional[Update] = None,
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
        
        # Get translations
        title = t('products.list.title', update) if update else "📋 DANH SÁCH SẢN PHẨM:"
        
        # Header
        lines.append(title)
        
        # Product list
        for idx, product in enumerate(products, start=1):
            product_num = (page - 1) * self.ITEMS_PER_PAGE + idx
            product_line = f"{product_num}. {product.name.upper()}"
            lines.append(product_line)
        
        # Footer with support info
        lines.append("")
        if update:
            footer_line_1 = t('products.list.footer_line_1', update, line1=SUPPORT_LINE_1)
            footer_line_2 = t('products.list.footer_line_2', update, line2=SUPPORT_LINE_2)
        else:
            footer_line_1 = SUPPORT_LINE_1
            footer_line_2 = SUPPORT_LINE_2
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
        for idx, product in enumerate(products, start=1):
            product_num = (page - 1) * self.ITEMS_PER_PAGE + idx
            button = InlineKeyboardButton(
                str(product_num),
                callback_data=f"product_{product.id}",
            )
            row.append(button)
            
            # Add row every 3 buttons
            if len(row) == 3:
                keyboard.append(row)
                row = []
        
        # Add remaining buttons
        if row:
            keyboard.append(row)
        
        # Navigation buttons
        nav_row = []
        if page > 1:
            prev_text = t('buttons.prev', update) if update else "◀ PREV PAGE"
            nav_row.append(
                InlineKeyboardButton(prev_text, callback_data=f"page_{page - 1}")
            )
        if page < total_pages:
            next_text = t('buttons.next', update) if update else "NEXT PAGE ▶"
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

