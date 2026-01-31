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
        Format product detail message with emoji-based design.
        
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
        title = t('products.detail.title', update) if update else "📋 DANH SÁCH SẢN PHẨM:"
        select_prompt = t('products.detail.select_prompt', update) if update else "👉 CHỌN SẢN PHẨM BÊN DƯỚI :"
        in_stock_template = t('products.detail.stock_available', update) if update else "(còn {stock})"
        out_of_stock = t('products.detail.out_of_stock', update) if update else "(hết hàng)"
        
        # Header
        lines.append(title)
        
        # Variations list
        if variations:
            for idx, variation in enumerate(variations, start=1):
                # Format price with thousand separators
                price_str = f"{variation.price:,}đ"
                stock_str = in_stock_template.format(stock=variation.stock) if variation.stock > 0 else out_of_stock
                var_line = f"{idx}. {product.name.upper()} {variation.name} — {price_str} {stock_str}"
                lines.append(var_line)
        
        # Selection prompt
        lines.append("")
        lines.append(select_prompt)
        
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

