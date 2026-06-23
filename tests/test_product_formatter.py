"""
Tests for product list formatter.
"""
import pytest
from telegram import InlineKeyboardMarkup
from src.bot.messages.product_formatter import ProductFormatter
from src.database.models import Product, DeliveryType


@pytest.fixture
def sample_products():
    products = []
    for i in range(5):
        products.append(
            Product(
                id=f"prod_{i}",
                name=f"Product {i}",
                description=f"Description {i}",
                delivery_type=DeliveryType.PRE_UPLOADED,
                is_active=True,
            )
        )
    return products


@pytest.fixture
def formatter():
    return ProductFormatter()


class TestProductFormatter:
    def test_format_product_list_without_custom_text_returns_non_empty_placeholder(self, formatter, sample_products):
        formatted = formatter.format_product_list()
        assert formatted == "\u200B"

    def test_format_product_list_custom_prompt(self, formatter, sample_products):
        formatted = formatter.format_product_list(
            product_choose_text="Pick one",
        )
        assert "Pick one" in formatted

    def test_create_product_keyboard_uses_product_names(self, formatter, sample_products):
        keyboard = formatter.create_product_keyboard(sample_products)

        assert isinstance(keyboard, InlineKeyboardMarkup)
        buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        product_buttons = [btn for btn in buttons if btn.callback_data and btn.callback_data.startswith("product_")]
        assert len(product_buttons) == 5
        assert product_buttons[0].text.startswith("Product")

    def test_create_product_keyboard_long_name_is_moved_to_bottom(self, formatter):
        products = [
            Product(
                id="short_1",
                name="Short",
                description="",
                delivery_type=DeliveryType.PRE_UPLOADED,
                is_active=True,
            ),
            Product(
                id="long_1",
                name="This is a very long product name that should be on its own row",
                description="",
                delivery_type=DeliveryType.PRE_UPLOADED,
                is_active=True,
            ),
            Product(
                id="short_2",
                name="Other",
                description="",
                delivery_type=DeliveryType.PRE_UPLOADED,
                is_active=True,
            ),
        ]

        keyboard = formatter.create_product_keyboard(products)
        rows = keyboard.inline_keyboard
        # Short products should stay in the top 3-column section.
        assert rows[0][0].callback_data == "product_short_1"
        assert rows[0][1].callback_data == "product_short_2"
        # Long product should be placed above the order-history row as a single-button row.
        assert rows[-2][0].callback_data == "product_long_1"
        assert len(rows[-2]) == 1

    def test_create_product_keyboard_uses_custom_emoji_icon(self, formatter):
        class FakeEmojiService:
            def get_first_emoji_id(self, placeholder_id):
                assert placeholder_id == 1
                return "5379748062124983193"

            def get_plain_text(self, placeholder_id):
                return "⭐"

        product = Product(
            id="prod_emoji",
            name="{emo:1} Claude",
            description="",
            delivery_type=DeliveryType.PRE_UPLOADED,
            is_active=True,
        )

        keyboard = formatter.create_product_keyboard([product], emoji_service=FakeEmojiService())
        button = keyboard.inline_keyboard[0][0]

        assert button.text == "Claude"
        assert button.icon_custom_emoji_id == "5379748062124983193"
