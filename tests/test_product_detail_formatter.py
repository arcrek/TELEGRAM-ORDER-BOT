"""
Tests for product detail formatter.
Following TDD: Write tests first, then implement formatter.
"""
import pytest
from telegram import InlineKeyboardMarkup
from src.bot.messages.product_detail_formatter import ProductDetailFormatter
from src.database.models import Product, ProductVariation, DeliveryType


@pytest.fixture
def sample_product():
    """Create a sample product for testing."""
    return Product(
        id="prod_1",
        name="ALIGHT MOTION",
        description="Video editing app with premium features",
        delivery_type=DeliveryType.PRE_UPLOADED,
        is_active=True,
    )


@pytest.fixture
def sample_variations():
    """Create sample variations for testing."""
    return [
        ProductVariation(
            id="var_1",
            product_id="prod_1",
            name="Pro 12M 1PCS",
            price=40000,
            stock=51,
            is_active=True,
        ),
        ProductVariation(
            id="var_2",
            product_id="prod_1",
            name="Pro 12m 50PCS",
            price=50000,
            stock=981,
            is_active=True,
        ),
        ProductVariation(
            id="var_3",
            product_id="prod_1",
            name="Pro 12m 100PCS",
            price=75000,
            stock=972,
            is_active=True,
        ),
    ]


@pytest.fixture
def formatter():
    """Create formatter instance."""
    return ProductDetailFormatter()


class TestProductDetailFormatter:
    """Test ProductDetailFormatter class."""

    def test_format_product_detail(self, formatter, sample_product, sample_variations):
        """Test formatting product detail message."""
        total_stock = sum(v.stock for v in sample_variations)
        formatted = formatter.format_product_detail(sample_product, sample_variations, total_stock)
        
        assert "ALIGHT MOTION" in formatted
        assert "Stock Total" in formatted or str(total_stock) in formatted
        assert "Detail" in formatted or "Description" in formatted
        assert "Variations" in formatted or "Prices" in formatted

    def test_format_product_detail_with_box_drawing(self, formatter, sample_product, sample_variations):
        """Test that formatted message uses box drawing characters."""
        total_stock = sum(v.stock for v in sample_variations)
        formatted = formatter.format_product_detail(sample_product, sample_variations, total_stock)
        
        # Check for box drawing characters
        assert "+" in formatted or "|" in formatted

    def test_format_variations_list(self, formatter, sample_variations):
        """Test formatting variations list."""
        formatted = formatter.format_variations_list(sample_variations)
        
        assert "Pro 12M 1PCS" in formatted
        assert "40000" in formatted or "40000" in formatted.replace(",", "")
        assert "51" in formatted

    def test_create_variation_keyboard(self, formatter, sample_variations):
        """Test creating inline keyboard for variations."""
        keyboard = formatter.create_variation_keyboard(sample_variations, "prod_1")
        
        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert len(keyboard.inline_keyboard) > 0
        
        # Check that variation buttons exist
        buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        variation_buttons = [btn for btn in buttons if btn.callback_data and btn.callback_data.startswith("variation_")]
        assert len(variation_buttons) == len(sample_variations)

    def test_create_product_detail_keyboard(self, formatter):
        """Test creating keyboard with refresh and back buttons."""
        keyboard = formatter.create_product_detail_keyboard("prod_1", page=1)
        
        assert isinstance(keyboard, InlineKeyboardMarkup)
        buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in buttons]
        
        # Should have refresh and back buttons
        assert any("refresh" in text.lower() or "Refresh" in text for text in button_texts)
        assert any("back" in text.lower() or "Back" in text for text in button_texts)

