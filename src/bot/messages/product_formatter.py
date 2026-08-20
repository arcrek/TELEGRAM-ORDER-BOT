"""
Product list formatter for Telegram messages.
"""
import unicodedata

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import KeyboardButtonStyle

from src.bot.messages.emoji_renderer import split_icon
from src.bot.utils.language import t
from src.database.models import Product
from src.database.models.enums import DeliveryType


class ProductFormatter:
    """Formatter for product list messages."""

    _LONG_NAME_ROW_THRESHOLD = 18

    @staticmethod
    def _display_width(text: str) -> int:
        """
        Approximate display width for Telegram buttons.
        Wide unicode chars count as 2 cells.
        """
        width = 0
        for ch in text:
            width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        return width

    def format_product_list(self, product_choose_text: str | None = None) -> str:
        """Return product choose text only."""
        if product_choose_text and product_choose_text.strip():
            return product_choose_text.strip()
        # Telegram requires non-empty message text.
        return "\u200b"

    def create_product_keyboard(
        self,
        products: list[Product],
        update: Update | None = None,
        pre_uploaded_in_stock_ids: set[str] | None = None,
        emoji_service=None,
    ) -> InlineKeyboardMarkup:
        """Create inline keyboard for product selection with order history button at bottom.

        When emoji_service is provided, the first {emo:id} token in a product
        name becomes the button's custom-emoji icon (Bot API 9.4) and is removed
        from the visible label; layout/width is computed on the cleaned label.
        """
        def _label_and_icon(product: Product) -> tuple[str, str | None]:
            if emoji_service is None:
                return product.name, None
            return split_icon(product.name, emoji_service)

        keyboard = []
        short_products = []
        long_products = []
        for product in products:
            label, icon = _label_and_icon(product)
            entry = (product, label, icon)
            if self._display_width(label) > self._LONG_NAME_ROW_THRESHOLD:
                long_products.append(entry)
            else:
                short_products.append(entry)

        def _button_style(product: Product) -> str | None:
            if product.delivery_type == DeliveryType.UPGRADE:
                return KeyboardButtonStyle.PRIMARY
            if product.delivery_type == DeliveryType.VIRTUAL_ORDER:
                return (
                    KeyboardButtonStyle.SUCCESS
                    if any(v.stock > 0 for v in product.variations)
                    else KeyboardButtonStyle.DANGER
                )
            if product.delivery_type == DeliveryType.PRE_UPLOADED:
                in_stock = (
                    product.id in pre_uploaded_in_stock_ids
                    if pre_uploaded_in_stock_ids is not None
                    else any(v.stock > 0 for v in product.variations)
                )
                return KeyboardButtonStyle.SUCCESS if in_stock else KeyboardButtonStyle.DANGER
            return None

        # Short-name products in 3-column layout.
        row = []
        for product, label, icon in short_products:
            row.append(
                InlineKeyboardButton(
                    label,
                    callback_data=f"product_{product.id}",
                    style=_button_style(product),
                    icon_custom_emoji_id=icon,
                )
            )
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        # Long-name products one per row.
        for product, label, icon in long_products:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        label,
                        callback_data=f"product_{product.id}",
                        style=_button_style(product),
                        icon_custom_emoji_id=icon,
                    )
                ]
            )

        order_history_text = t('buttons.order_history', update) if update else "📋 Order History"
        keyboard.append([InlineKeyboardButton(order_history_text, callback_data="order_history")])

        return InlineKeyboardMarkup(keyboard)
