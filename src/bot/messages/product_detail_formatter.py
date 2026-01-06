"""
Product detail formatter for Telegram messages.
"""
from typing import List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from src.database.models import Product, ProductVariation


class ProductDetailFormatter:
    """Formatter for product detail messages."""

    def format_product_detail(
        self,
        product: Product,
        variations: List[ProductVariation],
        total_stock: int,
    ) -> str:
        """
        Format product detail message with box drawing.
        
        Args:
            product: Product instance
            variations: List of ProductVariation instances
            total_stock: Total stock across all variations
        
        Returns:
            Formatted message string
        """
        lines = []
        
        # Product info header
        lines.append("+" + "─" * 37 + "+")
        lines.append(f"|・ Product: {product.name.upper()}")
        lines.append(f"|・ Stock Total: {total_stock}")
        if product.description:
            # Truncate description if too long
            desc = product.description[:30] + "..." if len(product.description) > 30 else product.description
            lines.append(f"|・ Detail: {desc}")
        lines.append("+" + "─" * 37 + "+")
        
        # Variations section
        if variations:
            lines.append("+" + "─" * 37 + "+")
            lines.append("| Variations, Prices & Stock:")
            for variation in variations:
                var_line = f"|・ {variation.name}: {variation.price:,} - Stock: {variation.stock}"
                lines.append(var_line)
            lines.append("+" + "─" * 37 + "+")
        
        return "\n".join(lines)

    def format_variations_list(self, variations: List[ProductVariation]) -> str:
        """
        Format variations list text.
        
        Args:
            variations: List of ProductVariation instances
        
        Returns:
            Formatted variations text
        """
        lines = []
        for variation in variations:
            lines.append(f"・ {variation.name}: {variation.price:,} VND - Stock: {variation.stock}")
        return "\n".join(lines)

    def create_variation_keyboard(
        self,
        variations: List[ProductVariation],
        product_id: str,
    ) -> InlineKeyboardMarkup:
        """
        Create inline keyboard for variation selection.
        
        Args:
            variations: List of ProductVariation instances
            product_id: Product ID (for back button)
        
        Returns:
            InlineKeyboardMarkup instance
        """
        keyboard = []
        
        # Variation buttons (2 per row)
        row = []
        for variation in variations:
            button = InlineKeyboardButton(
                variation.name,
                callback_data=f"variation_{variation.id}",
            )
            row.append(button)
            
            if len(row) == 2:
                keyboard.append(row)
                row = []
        
        # Add remaining button
        if row:
            keyboard.append(row)
        
        # Action buttons
        action_row = [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_product"),
            InlineKeyboardButton("◀ Back to list", callback_data="back_to_list"),
        ]
        keyboard.append(action_row)
        
        return InlineKeyboardMarkup(keyboard)

    def create_product_detail_keyboard(
        self,
        product_id: str,
        page: int = 1,
        variations: List[ProductVariation] = None,
    ) -> InlineKeyboardMarkup:
        """
        Create inline keyboard for product detail view.
        
        Args:
            product_id: Product ID
            page: Current page number (for back button)
            variations: List of variations (if provided, shows variation buttons)
        
        Returns:
            InlineKeyboardMarkup instance
        """
        keyboard = []
        
        # Add variation buttons if provided
        if variations:
            # Variation buttons (2 per row)
            row = []
            for variation in variations:
                button = InlineKeyboardButton(
                    variation.name,
                    callback_data=f"variation_{variation.id}",
                )
                row.append(button)
                
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            
            # Add remaining button
            if row:
                keyboard.append(row)
        
        # Action buttons
        action_row = [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_product"),
            InlineKeyboardButton("◀ Back to list", callback_data="back_to_list"),
        ]
        keyboard.append(action_row)
        
        return InlineKeyboardMarkup(keyboard)

