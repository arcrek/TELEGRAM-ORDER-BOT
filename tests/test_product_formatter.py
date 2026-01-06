"""
Tests for product list formatter.
Following TDD: Write tests first, then implement formatter.
"""
import pytest
from telegram import InlineKeyboardMarkup
from src.bot.messages.product_formatter import ProductFormatter
from src.database.models import Product, DeliveryType


@pytest.fixture
def sample_products():
    """Create sample products for testing."""
    products = []
    for i in range(15):
        product = Product(
            id=f"prod_{i}",
            name=f"PRODUCT {i}",
            description=f"Description {i}",
            delivery_type=DeliveryType.PRE_UPLOADED,
            is_active=True,
        )
        products.append(product)
    return products


@pytest.fixture
def formatter():
    """Create formatter instance."""
    return ProductFormatter()


class TestProductFormatter:
    """Test ProductFormatter class."""

    def test_format_product_list_page(self, formatter, sample_products):
        """Test formatting product list for a page."""
        # Format first page (15 items)
        page_products = sample_products[:15]
        formatted = formatter.format_product_list(page_products, page=1, total_pages=1)
        
        assert "LIST PRODUCT" in formatted
        assert "page 1 / 1" in formatted
        assert "[1] PRODUCT 0" in formatted
        assert "[15] PRODUCT 14" in formatted

    def test_format_product_list_with_box_drawing(self, formatter, sample_products):
        """Test that formatted message uses box drawing characters."""
        page_products = sample_products[:15]
        formatted = formatter.format_product_list(page_products, page=1, total_pages=1)
        
        # Check for box drawing characters
        assert "+" in formatted or "|" in formatted

    def test_format_product_list_pagination(self, formatter, sample_products):
        """Test formatting with pagination."""
        # Format second page
        page_products = sample_products[15:30] if len(sample_products) > 15 else []
        if page_products:
            formatted = formatter.format_product_list(page_products, page=2, total_pages=2)
            assert "page 2 / 2" in formatted

    def test_create_product_keyboard(self, formatter, sample_products):
        """Test creating inline keyboard for products."""
        page_products = sample_products[:15]
        keyboard = formatter.create_product_keyboard(page_products, page=1, total_pages=1)
        
        assert isinstance(keyboard, InlineKeyboardMarkup)
        assert len(keyboard.inline_keyboard) > 0
        
        # Check that product buttons exist
        buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        product_buttons = [btn for btn in buttons if btn.callback_data and btn.callback_data.startswith("product_")]
        assert len(product_buttons) == 15

    def test_create_product_keyboard_with_navigation(self, formatter, sample_products):
        """Test keyboard includes navigation buttons when needed."""
        page_products = sample_products[:15]
        keyboard = formatter.create_product_keyboard(page_products, page=1, total_pages=2)
        
        buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in buttons]
        
        # Should have next page button
        assert any("NEXT" in text.upper() or ">" in text for text in button_texts)

    def test_create_product_keyboard_prev_button(self, formatter, sample_products):
        """Test keyboard includes previous button on later pages."""
        page_products = sample_products[15:30] if len(sample_products) > 15 else []
        if page_products:
            keyboard = formatter.create_product_keyboard(page_products, page=2, total_pages=2)
            
            buttons = [btn for row in keyboard.inline_keyboard for btn in row]
            button_texts = [btn.text for btn in buttons]
            
            # Should have previous page button
            assert any("PREV" in text.upper() or "<" in text for text in button_texts)

    def test_calculate_total_pages(self, formatter):
        """Test calculating total pages."""
        assert formatter.calculate_total_pages(15, 15) == 1
        assert formatter.calculate_total_pages(16, 15) == 2
        assert formatter.calculate_total_pages(30, 15) == 2
        assert formatter.calculate_total_pages(31, 15) == 3

