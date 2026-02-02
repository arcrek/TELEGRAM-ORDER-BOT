"""
Order confirmation formatter for Telegram messages.
"""
from typing import Optional, Tuple
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
        bonus_quantity: int = 0,
        bonus_label: Optional[str] = None,
    ) -> str:
        """
        Format order confirmation message with emoji-based design.
        
        Args:
            product: Product instance
            variation: ProductVariation instance
            quantity: Order quantity
            update: Telegram update object for translations
            bonus_quantity: Number of bonus items (0 if no bonus)
            bonus_label: Label for bonus (e.g., "Mua 10 tặng 2")
        
        Returns:
            Formatted message string
        """
        total = self.calculate_total(variation.price, quantity)
        total_items = quantity + bonus_quantity
        
        # Get translations
        title = t('products.order_confirmation.title', update) if update else "✅ XÁC NHẬN THANH TOÁN 🛒"
        product_label = t('products.order_confirmation.product', update) if update else "📌 Sản phẩm"
        variation_label = t('products.order_confirmation.variation', update) if update else "➕ Loại"
        unit_price_label = t('products.order_confirmation.unit_price', update) if update else "💵 Đơn giá"
        in_stock_label = t('products.order_confirmation.in_stock', update) if update else "📦 Còn"
        order_quantity_label = t('products.order_confirmation.order_quantity', update) if update else "👉 Số lượng đặt hàng"
        total_payment_label = t('products.order_confirmation.total_payment', update) if update else "💵 Tổng tiền"
        
        lines = []
        
        # Header
        lines.append(title)
        lines.append(f"{product_label}: {product.name}")
        lines.append(f"{variation_label}: {variation.name}")
        lines.append(f"{unit_price_label}: {variation.price:,} VND")
        lines.append(f"{in_stock_label}: {variation.stock}")
        lines.append("")
        lines.append(f"{order_quantity_label}: x{quantity}")
        
        # Add bonus line if applicable
        if bonus_quantity > 0 and bonus_label:
            bonus_text = t('products.order_confirmation.bonus', update) if update else "🎁 Bonus"
            lines.append(f"{bonus_text}: +{bonus_quantity} ({bonus_label})")
        
        # Total payment line with item count if bonus
        if bonus_quantity > 0:
            total_items_text = t('products.order_confirmation.total_items', update) if update else "({total} sản phẩm)"
            total_items_text = total_items_text.format(total=total_items)
            lines.append(f"{total_payment_label}: {total:,} VND {total_items_text}")
        else:
            lines.append(f"{total_payment_label}: {total:,} VND")
        
        return "\n".join(lines)

    def get_applicable_bonus(
        self,
        variation_id: str,
        quantity: int,
        stock: int,
        session,
        language: str = 'vi',
    ) -> Tuple[int, Optional[str]]:
        """
        Get applicable bonus for a given quantity and stock.
        
        Args:
            variation_id: Variation ID
            quantity: Order quantity
            stock: Available stock
            session: Database session
            language: Language code
        
        Returns:
            Tuple of (bonus_quantity, bonus_label) or (0, None) if no bonus
        """
        from src.database.services.bonus_tier_service import BonusTierService
        
        bonus_service = BonusTierService(session)
        tier = bonus_service.get_applicable_bonus(variation_id, quantity, stock)
        
        if tier:
            if language == 'en':
                label = f"Buy {tier.min_quantity} get {tier.bonus_quantity} free"
            else:
                label = f"Mua {tier.min_quantity} tặng {tier.bonus_quantity}"
            return tier.bonus_quantity, label
        
        return 0, None

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
        
        if adjustment_row:
            keyboard.append(adjustment_row)
        
        # Custom button (only if stock > 1) + Cancel button row
        cancel_text = t('products.order_confirmation.cancel', update) if update else "❌ Cancel"
        action_row = []
        
        # Only show custom button if there's more than 1 item in stock
        if max_stock > 1:
            custom_text = t('products.order_confirmation.custom', update) if update else "⚙️ Tuỳ chọn số lượng"
            action_row.append(InlineKeyboardButton(custom_text, callback_data=f"qty_custom_{variation_id}"))
        
        action_row.append(InlineKeyboardButton(cancel_text, callback_data="back_to_list"))
        keyboard.append(action_row)
        
        # Proceed payment button
        proceed_text = t('products.order_confirmation.proceed_payment', update) if update else "💳 Proceed payment"
        keyboard.append([
            InlineKeyboardButton(proceed_text, callback_data=f"payment_{variation_id}")
        ])
        
        return InlineKeyboardMarkup(keyboard)

