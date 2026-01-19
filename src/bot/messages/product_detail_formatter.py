"""
Product detail formatter for Telegram messages.
"""
from typing import List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from src.database.models import Product, ProductVariation
from src.bot.utils.language import t


class ProductDetailFormatter:
    """Formatter for product detail messages."""

    def format_product_detail(
        self,
        product: Product,
        variations: List[ProductVariation],
        total_stock: int,
        update: Optional[Update] = None,
    ) -> str:
        """
        Format product detail message with box drawing.
        
        Args:
            product: Product instance
            variations: List of ProductVariation instances
            total_stock: Total stock across all variations
            update: Telegram update object for translations
        
        Returns:
            Formatted message string
        """
        lines = []
        
        # Get translations
        product_label = t('products.detail.product_label', update) if update else "・ Product"
        stock_total = t('products.detail.stock_total', update) if update else "・ Stock Total"
        detail_label = t('products.detail.detail_label', update) if update else "・ Detail"
        variations_header = t('products.detail.variations_header', update) if update else "Variations, Prices & Stock"
        
        # Product info header
        lines.append("+" + "─" * 37 + "+")
        lines.append(f"|{product_label}: {product.name.upper()}")
        lines.append(f"|{stock_total}: {total_stock}")
        if product.description:
            # Truncate description if too long
            desc = product.description[:30] + "..." if len(product.description) > 30 else product.description
            lines.append(f"|{detail_label}: {desc}")
        lines.append("+" + "─" * 37 + "+")
        
        # Variations section
        if variations:
            lines.append("+" + "─" * 37 + "+")
            lines.append(f"| {variations_header}:")
            for variation in variations:
                var_line_template = t('products.detail.variation_line', update) if update else "・ {name}: {price} - Stock: {stock}"
                var_line = var_line_template.format(
                    name=variation.name,
                    price=f"{variation.price:,}",
                    stock=variation.stock
                )
                lines.append(f"|{var_line}")
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
        update: Optional[Update] = None,
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
        refresh_text = t('products.detail.refresh', update) if update else "🔄 Refresh"
        back_text = t('products.detail.back_to_list', update) if update else "◀ Back to list"
        action_row = [
            InlineKeyboardButton(refresh_text, callback_data="refresh_product"),
            InlineKeyboardButton(back_text, callback_data="back_to_list"),
        ]
        keyboard.append(action_row)
        
        return InlineKeyboardMarkup(keyboard)

    def create_product_detail_keyboard(
        self,
        product_id: str,
        page: int = 1,
        variations: List[ProductVariation] = None,
        update: Optional[Update] = None,
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
        refresh_text = t('products.detail.refresh', update) if update else "🔄 Refresh"
        back_text = t('products.detail.back_to_list', update) if update else "◀ Back to list"
        action_row = [
            InlineKeyboardButton(refresh_text, callback_data="refresh_product"),
            InlineKeyboardButton(back_text, callback_data="back_to_list"),
        ]
        keyboard.append(action_row)
        
        return InlineKeyboardMarkup(keyboard)

