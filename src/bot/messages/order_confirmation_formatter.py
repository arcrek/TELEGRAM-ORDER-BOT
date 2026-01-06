"""
Order confirmation formatter for Telegram messages.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from src.database.models import Product, ProductVariation


class OrderConfirmationFormatter:
    """Formatter for order confirmation messages."""

    def format_order_confirmation(
        self,
        product: Product,
        variation: ProductVariation,
        quantity: int,
    ) -> str:
        """
        Format order confirmation message with box drawing.
        
        Args:
            product: Product instance
            variation: ProductVariation instance
            quantity: Order quantity
        
        Returns:
            Formatted message string
        """
        total = self.calculate_total(variation.price, quantity)
        
        lines = []
        
        # Header
        lines.append("ORDER CONFIRMATION 🛒")
        lines.append("+" + "─" * 39 + "+")
        lines.append(f"|・Product: {product.name}")
        lines.append(f"|・Variation: {variation.name}")
        lines.append(f"|・Unit price: {variation.price:,} VND")
        lines.append(f"|・In stock: {variation.stock}")
        lines.append("|" + "─" * 39 + "|")
        lines.append(f"|・Order Quantity: x{quantity}")
        lines.append(f"|・Total Payment: {total:,} VND")
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
        
        if adjustment_row:
            keyboard.append(adjustment_row)
        
        # Proceed payment button
        keyboard.append([
            InlineKeyboardButton("💳 Proceed payment", callback_data=f"payment_{variation_id}")
        ])
        
        return InlineKeyboardMarkup(keyboard)

