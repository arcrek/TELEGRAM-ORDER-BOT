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
        formatted = formatter.format_product_list(sample_products, page=1, total_pages=1)
        assert formatted == "\u200B"

    def test_format_product_list_custom_prompt(self, formatter, sample_products):
        formatted = formatter.format_product_list(
            sample_products,
            page=1,
            total_pages=1,
            product_choose_text="Pick one",
        )
        assert "Pick one" in formatted

    def test_create_product_keyboard_uses_product_names(self, formatter, sample_products):
        keyboard = formatter.create_product_keyboard(sample_products, page=1, total_pages=1)

        assert isinstance(keyboard, InlineKeyboardMarkup)
        buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        product_buttons = [btn for btn in buttons if btn.callback_data and btn.callback_data.startswith("product_")]
        assert len(product_buttons) == 5
        assert product_buttons[0].text.startswith("Product")

    def test_create_product_keyboard_long_name_in_separate_row(self, formatter):
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

        keyboard = formatter.create_product_keyboard(products, page=1, total_pages=1)
        rows = keyboard.inline_keyboard
        assert any(len(row) == 1 and row[0].callback_data == "product_long_1" for row in rows)

    def test_calculate_total_pages(self, formatter):
        assert formatter.calculate_total_pages(15, 15) == 1
        assert formatter.calculate_total_pages(16, 15) == 2

