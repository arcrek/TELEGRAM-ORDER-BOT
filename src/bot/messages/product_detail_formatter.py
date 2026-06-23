"""
Product detail formatter for Telegram messages.
"""

from typing import List, Optional, Dict, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import KeyboardButtonStyle
from src.database.models import Product, ProductVariation
from src.database.models.enums import DeliveryType
from src.bot.messages.emoji_renderer import split_icon
from src.bot.utils.language import t


class ProductDetailFormatter:
    """Formatter for product detail messages."""

    _BUTTON_TEXT_MAX_LEN = 55
    # Stock values >= this are treated as "unlimited" (no inventory tracking).
    # Set by callers for UPGRADE-delivery products; renderers omit the stock
    # segment so the customer doesn't see a meaningless large number.
    _UNLIMITED_STOCK_THRESHOLD = 999_999

    @staticmethod
    def _truncate_button_text(text: str, max_len: int = 55) -> str:
        if len(text) <= max_len:
            return text
        return f"{text[: max_len - 1]}..."

    def _variation_button_text(
        self,
        variation: ProductVariation,
        update: Optional[Update] = None,
        emoji_service=None,
    ) -> Tuple[str, Optional[str]]:
        """Return (button_label, icon_custom_emoji_id).

        The first {emo:id} token in the variation name becomes the button's
        custom-emoji icon (Bot API 9.4) and is stripped from the label.
        """
        name, icon = (variation.name, None)
        if emoji_service is not None:
            name, icon = split_icon(variation.name, emoji_service)
        price_str = f"{variation.price:,}d"
        if variation.stock >= self._UNLIMITED_STOCK_THRESHOLD:
            text = f"{name} • {price_str}"
        else:
            if variation.stock > 0:
                stock_str = str(variation.stock)
            else:
                stock_str = (
                    t("products.detail.out_of_stock", update)
                    if update
                    else "out of stock"
                )
            text = f"{name} • {price_str} • {stock_str}"
        return self._truncate_button_text(text, self._BUTTON_TEXT_MAX_LEN), icon

    def format_product_detail(
        self,
        product: Product,
        variations: List[ProductVariation],
        total_stock: int,
        update: Optional[Update] = None,
        bonus_texts: Optional[Dict[str, str]] = None,
        variation_choose_text: Optional[str] = None,
        sold_count: int = 0,
    ) -> str:
        """
        Format product detail message with emoji-based design.

        Args:
            product: Product instance
            variations: List of ProductVariation instances
            total_stock: Total stock across all variations
            update: Telegram update object for translations
            bonus_texts: Optional dict mapping variation_id to bonus display text

        Returns:
            Formatted message string
        """
        lines = []

        # Get translations
        title = t("products.detail.title", update) if update else "PRODUCT LIST"
        select_prompt = (
            variation_choose_text.strip()
            if variation_choose_text and variation_choose_text.strip()
            else (
                t("products.detail.select_prompt", update)
                if update
                else "Choose variation below"
            )
        )
        in_stock_template = (
            t("products.detail.stock_available", update)
            if update
            else "(in stock: {stock})"
        )
        out_of_stock = (
            t("products.detail.out_of_stock", update) if update else "(out of stock)"
        )

        # Header
        lines.append(title)

        # Sold count
        if sold_count > 0:
            sold_template = (
                t("products.detail.sold_count", update)
                if update
                else "🔥 Đã bán: {count}"
            )
            lines.append(sold_template.format(count=f"{sold_count:,}"))

        # Product description (if set)
        if product.description and product.description.strip():
            lines.append("")
            lines.append(product.description.strip())

        # Variations list
        if variations:
            for idx, variation in enumerate(variations, start=1):
                price_str = f"{variation.price:,}d"
                if variation.stock >= self._UNLIMITED_STOCK_THRESHOLD:
                    stock_str = ""
                elif variation.stock > 0:
                    stock_str = in_stock_template.format(stock=variation.stock)
                else:
                    stock_str = out_of_stock

                bonus_str = ""
                if bonus_texts and variation.id in bonus_texts:
                    bonus_str = f" {bonus_texts[variation.id]}"

                stock_segment = f" {stock_str}" if stock_str else ""
                var_line = f"{idx}. {product.name.upper()} {variation.name} - {price_str}{stock_segment}{bonus_str}"
                lines.append(var_line)

        lines.append("")
        lines.append(select_prompt)

        return "\n".join(lines)

    def get_bonus_texts_for_variations(
        self,
        variation_ids: List[str],
        session,
        language: str = "vi",
    ) -> Dict[str, str]:
        """
        Get bonus display texts for multiple variations.

        Args:
            variation_ids: List of variation IDs
            session: Database session
            language: Language code ('vi' or 'en')

        Returns:
            Dict mapping variation_id to bonus text
        """
        from src.database.services.bonus_tier_service import BonusTierService

        bonus_service = BonusTierService(session)
        all_tiers = bonus_service.get_all_bonus_tiers_for_variations(variation_ids)

        result = {}
        for variation_id, tiers in all_tiers.items():
            if tiers:
                first_tier = tiers[0]
                if language == "en":
                    result[variation_id] = (
                        f"(Buy {first_tier.min_quantity} get {first_tier.bonus_quantity} free)"
                    )
                else:
                    result[variation_id] = (
                        f"(Mua {first_tier.min_quantity} tặng {first_tier.bonus_quantity})"
                    )

        return result

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
            lines.append(
                f"- {variation.name}: {variation.price:,} VND - Stock: {variation.stock}"
            )
        return "\n".join(lines)

    def _variation_style(
        self, variation: ProductVariation, delivery_type: Optional[str]
    ) -> Optional[str]:
        if delivery_type == DeliveryType.UPGRADE:
            return KeyboardButtonStyle.PRIMARY
        if delivery_type == DeliveryType.PRE_UPLOADED:
            return (
                KeyboardButtonStyle.SUCCESS
                if variation.stock > 0
                else KeyboardButtonStyle.DANGER
            )
        return None

    def create_variation_keyboard(
        self,
        variations: List[ProductVariation],
        product_id: str,
        update: Optional[Update] = None,
        delivery_type: Optional[str] = None,
        emoji_service=None,
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
            label, icon = self._variation_button_text(variation, update, emoji_service)
            button = InlineKeyboardButton(
                label,
                callback_data=f"variation_{variation.id}",
                style=self._variation_style(variation, delivery_type),
                icon_custom_emoji_id=icon,
            )
            row.append(button)

            if len(row) == 2:
                keyboard.append(row)
                row = []

        if row:
            keyboard.append(row)

        refresh_text = t("products.detail.refresh", update) if update else "Refresh"
        back_text = (
            t("products.detail.back_to_list", update) if update else "Back to list"
        )
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
        delivery_type: Optional[str] = None,
        emoji_service=None,
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

        if variations:
            row = []
            for variation in variations:
                label, icon = self._variation_button_text(variation, update, emoji_service)
                button = InlineKeyboardButton(
                    label,
                    callback_data=f"variation_{variation.id}",
                    style=self._variation_style(variation, delivery_type),
                    icon_custom_emoji_id=icon,
                )
                row.append(button)

                if len(row) == 2:
                    keyboard.append(row)
                    row = []

            if row:
                keyboard.append(row)

        refresh_text = t("products.detail.refresh", update) if update else "Refresh"
        back_text = (
            t("products.detail.back_to_list", update) if update else "Back to list"
        )
        action_row = [
            InlineKeyboardButton(refresh_text, callback_data="refresh_product"),
            InlineKeyboardButton(back_text, callback_data="back_to_list"),
        ]
        manual_text = t("products.detail.manual", update) if update else "📖 User Guide"
        manual_row = [
            InlineKeyboardButton(manual_text, callback_data=f"manual_list_{product_id}")
        ]
        keyboard.append(manual_row)
        keyboard.append(action_row)

        return InlineKeyboardMarkup(keyboard)
