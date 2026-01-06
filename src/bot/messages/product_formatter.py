"""
Product list formatter for Telegram messages.
"""
from typing import List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from src.database.models import Product


class ProductFormatter:
    """Formatter for product list messages."""

    ITEMS_PER_PAGE = 15

    def format_product_list(
        self,
        products: List[Product],
        page: int,
        total_pages: int,
    ) -> str:
        """
        Format product list message with box drawing.
        
        Args:
            products: List of Product instances
            page: Current page number
            total_pages: Total number of pages
        
        Returns:
            Formatted message string
        """
        lines = []
        
        # Header with box drawing
        lines.append("+" + "─" * 35 + "+")
        lines.append("|  LIST PRODUCT")
        lines.append(f"|  page {page} / {total_pages}")
        lines.append("|" + "─" * 35 + "|")
        
        # Product list
        for idx, product in enumerate(products, start=1):
            product_num = (page - 1) * self.ITEMS_PER_PAGE + idx
            product_line = f"| [{product_num}] {product.name.upper()}"
            lines.append(product_line)
        
        # Footer
        lines.append("+" + "─" * 35 + "+")
        
        return "\n".join(lines)

    def create_product_keyboard(
        self,
        products: List[Product],
        page: int,
        total_pages: int,
    ) -> InlineKeyboardMarkup:
        """
        Create inline keyboard for product selection.
        
        Args:
            products: List of Product instances
            page: Current page number
            total_pages: Total number of pages
        
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
            nav_row.append(
                InlineKeyboardButton("◀ PREV PAGE", callback_data=f"page_{page - 1}")
            )
        if page < total_pages:
            nav_row.append(
                InlineKeyboardButton("NEXT PAGE ▶", callback_data=f"page_{page + 1}")
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

