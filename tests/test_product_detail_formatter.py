"""
Tests for product detail formatter.
"""
import pytest
from telegram import InlineKeyboardMarkup
from src.bot.messages.product_detail_formatter import ProductDetailFormatter
from src.database.models import Product, ProductVariation, DeliveryType


@pytest.fixture
def sample_product():
    return Product(
        id="prod_1",
        name="ChatGPT",
        description="Subscription plans",
        delivery_type=DeliveryType.PRE_UPLOADED,
        is_active=True,
    )


@pytest.fixture
def sample_variations():
    return [
        ProductVariation(
            id="var_1",
            product_id="prod_1",
            name="Business 5 slots",
            price=100000,
            stock=8,
            is_active=True,
        ),
        ProductVariation(
            id="var_2",
            product_id="prod_1",
            name="Hotmail BHF",
            price=150000,
            stock=0,
            is_active=True,
        ),
    ]


@pytest.fixture
def formatter():
    return ProductDetailFormatter()


class TestProductDetailFormatter:
    def test_format_product_detail_contains_variations_and_prompt(self, formatter, sample_product, sample_variations):
        total_stock = sum(v.stock for v in sample_variations)
        formatted = formatter.format_product_detail(sample_product, sample_variations, total_stock)

        assert "CHATGPT" in formatted
        assert "Business 5 slots" in formatted

    def test_format_product_detail_custom_prompt(self, formatter, sample_product, sample_variations):
        total_stock = sum(v.stock for v in sample_variations)
        formatted = formatter.format_product_detail(
            sample_product,
            sample_variations,
            total_stock,
            variation_choose_text="Choose package",
        )

        assert "Choose package" in formatted

    def test_create_product_detail_keyboard_shows_name_price_stock(self, formatter, sample_variations):
        keyboard = formatter.create_product_detail_keyboard("prod_1", variations=sample_variations)

        assert isinstance(keyboard, InlineKeyboardMarkup)
        buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        variation_buttons = [btn for btn in buttons if btn.callback_data and btn.callback_data.startswith("variation_")]
        assert len(variation_buttons) == 2
        assert "100,000d" in variation_buttons[0].text
        assert "8" in variation_buttons[0].text

    def test_create_product_detail_keyboard_uses_custom_emoji_icon(self, formatter):
        class FakeEmojiService:
            def get_first_emoji_id(self, placeholder_id):
                assert placeholder_id == 2
                return "5379748062124983193"

            def get_plain_text(self, placeholder_id):
                return "⭐"

        variation = ProductVariation(
            id="var_emoji",
            product_id="prod_1",
            name="{emo:2} Pro 1 Month",
            price=99000,
            stock=5,
            is_active=True,
        )

        keyboard = formatter.create_product_detail_keyboard(
            "prod_1",
            variations=[variation],
            emoji_service=FakeEmojiService(),
        )
        button = keyboard.inline_keyboard[0][0]

        assert button.text.startswith("Pro 1 Month")
        assert "{emo:" not in button.text
        assert button.icon_custom_emoji_id == "5379748062124983193"
