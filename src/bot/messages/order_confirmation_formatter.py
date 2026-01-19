"""
Order confirmation formatter for Telegram messages.
"""
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from src.database.models import Product, ProductVariation
from src.bot.utils.language import t


class OrderConfirmationFormatter:
    """Formatter for order confirmation messages."""

    def format_order_confirmation(
        self,
        product: Product,
        variation: ProductVariation,
        quantity: int,
        update: Optional[Update] = None,
    ) -> str:
        """
        Format order confirmation message with box drawing.
        
        Args:
            product: Product instance
            variation: ProductVariation instance
            quantity: Order quantity
            update: Telegram update object for translations
        
        Returns:
            Formatted message string
        """
        total = self.calculate_total(variation.price, quantity)
        
        # Get translations
        title = t('products.order_confirmation.title', update) if update else "ORDER CONFIRMATION 🛒"
        product_label = t('products.order_confirmation.product', update) if update else "・Product"
        variation_label = t('products.order_confirmation.variation', update) if update else "・Variation"
        unit_price_label = t('products.order_confirmation.unit_price', update) if update else "・Unit price"
        in_stock_label = t('products.order_confirmation.in_stock', update) if update else "・In stock"
        order_quantity_label = t('products.order_confirmation.order_quantity', update) if update else "・Order Quantity"
        total_payment_label = t('products.order_confirmation.total_payment', update) if update else "・Total Payment"
        
        lines = []
        
        # Header
        lines.append(title)
        lines.append("+" + "─" * 39 + "+")
        lines.append(f"|{product_label}: {product.name}")
        lines.append(f"|{variation_label}: {variation.name}")
        lines.append(f"|{unit_price_label}: {variation.price:,} VND")
        lines.append(f"|{in_stock_label}: {variation.stock}")
        lines.append("|" + "─" * 39 + "|")
        lines.append(f"|{order_quantity_label}: x{quantity}")
        lines.append(f"|{total_payment_label}: {total:,} VND")
        lines.append("+" + "─" * 39 + "+")
        
        return "\n".join(lines)

    def calculate_total(self, unit_price: int, quantity: int) -> int:
        """
        Calculate total price.
        
        Args:
            unit_price: Price per unit
            quantity: Quantity
        
        Returns:
            Total price
        """
        return unit_price * quantity

    def validate_quantity(self, quantity: int, max_stock: int) -> int:
        """
        Validate and adjust quantity.
        
        Args:
            quantity: Requested quantity
            max_stock: Maximum available stock
        
        Returns:
            Validated quantity (between 1 and max_stock)
        """
        if quantity < 1:
            return 1
        if quantity > max_stock:
            return max_stock
        return quantity

    def create_quantity_keyboard(
        self,
        variation_id: str,
        quantity: int,
        max_stock: int,
        update: Optional[Update] = None,
    ) -> InlineKeyboardMarkup:
        """
        Create inline keyboard for quantity adjustment.
        
        Args:
            variation_id: Variation ID
            quantity: Current quantity
            max_stock: Maximum available stock
        
        Returns:
            InlineKeyboardMarkup instance
        """
        keyboard = []
        
        # Quantity adjustment buttons
        adjustment_row = []
        
        # +1 button (only if not at max)
        if quantity < max_stock:
            adjustment_row.append(
                InlineKeyboardButton("+1", callback_data=f"qty_{variation_id}_+1")
            )
        
        # +5 button (only if adding 5 won't exceed max)
        if quantity + 5 <= max_stock:
            adjustment_row.append(
                InlineKeyboardButton("+5", callback_data=f"qty_{variation_id}_+5")
            )
        
        # -1 button (only if quantity > 1)
        if quantity > 1:
            adjustment_row.append(
                InlineKeyboardButton("-1", callback_data=f"qty_{variation_id}_-1")
            )
        
        # -5 button (only if quantity > 5)
        if quantity > 5:
            adjustment_row.append(
                InlineKeyboardButton("-5", callback_data=f"qty_{variation_id}_-5")
            )
        
        # Custom button - always show it
        custom_text = t('products.order_confirmation.custom', update) if update else "⚙️ Custom"
        adjustment_row.append(
            InlineKeyboardButton(custom_text, callback_data=f"qty_custom_{variation_id}")
        )
        
        if adjustment_row:
            keyboard.append(adjustment_row)
        
        # Proceed payment button
        proceed_text = t('products.order_confirmation.proceed_payment', update) if update else "💳 Proceed payment"
        keyboard.append([
            InlineKeyboardButton(proceed_text, callback_data=f"payment_{variation_id}")
        ])
        
        return InlineKeyboardMarkup(keyboard)

