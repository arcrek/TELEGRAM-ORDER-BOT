"""
Tests for order confirmation formatter.
Following TDD: Write tests first, then implement formatter.
"""
import pytest
from telegram import InlineKeyboardMarkup
from src.bot.messages.order_confirmation_formatter import OrderConfirmationFormatter
from src.database.models import Product, ProductVariation, DeliveryType


@pytest.fixture
def sample_product():
    """Create a sample product for testing."""
    return Product(
        id="prod_1",
        name="Alight Motion",
        description="Video editing app",
        delivery_type=DeliveryType.PRE_UPLOADED,
        is_active=True,
    )


@pytest.fixture
def sample_variation():
    """Create a sample variation for testing."""
    return ProductVariation(
        id="var_1",
        product_id="prod_1",
        name="Pro 12B 1PCS",
        price=40000,
        stock=51,
        is_active=True,
    )


@pytest.fixture
def formatter():
    """Create formatter instance."""
    return OrderConfirmationFormatter()


class TestOrderConfirmationFormatter:
    """Test OrderConfirmationFormatter class."""

    def test_format_order_confirmation(self, formatter, sample_product, sample_variation):
        """Test formatting order confirmation message."""
        quantity = 1
        formatted = formatter.format_order_confirmation(
            sample_product, sample_variation, quantity
        )
        
        assert "ORDER CONFIRMATION" in formatted or "Order" in formatted
        assert "Alight Motion" in formatted
        assert "Pro 12B 1PCS" in formatted
        assert "40000" in formatted.replace(",", "")
        assert "51" in formatted
        assert "x1" in formatted or "Quantity: 1" in formatted

    def test_format_order_confirmation_with_box_drawing(self, formatter, sample_product, sample_variation):
        """Test that formatted message uses box drawing characters."""
        formatted = formatter.format_order_confirmation(
            sample_product, sample_variation, 1
        )
        
        # Check for box drawing characters
        assert "+" in formatted or "|" in formatted

    def test_calculate_total(self, formatter):
        """Test calculating total price."""
        assert formatter.calculate_total(40000, 1) == 40000
        assert formatter.calculate_total(40000, 5) == 200000
        assert formatter.calculate_total(50000, 2) == 100000

    def test_create_quantity_keyboard(self, formatter):
        """Test creating keyboard with quantity adjustment buttons."""
        keyboard = formatter.create_quantity_keyboard("var_1", quantity=1, max_stock=51)
        
        assert isinstance(keyboard, InlineKeyboardMarkup)
        buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in buttons]
        
        # Should have quantity adjustment buttons
        assert any("+1" in text or "+5" in text for text in button_texts)
        # When quantity is 1, there should be no decrease buttons
        # (quantity can't go below 1)
        assert not any("-1" in text or "-5" in text for text in button_texts)
        assert any("payment" in text.lower() or "Proceed" in text for text in button_texts)
    
    def test_create_quantity_keyboard_with_decrease_buttons(self, formatter):
        """Test keyboard shows decrease buttons when quantity > 1."""
        keyboard = formatter.create_quantity_keyboard("var_1", quantity=5, max_stock=51)
        
        assert isinstance(keyboard, InlineKeyboardMarkup)
        buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in buttons]
        
        # Should have both increase and decrease buttons when quantity > 1
        assert any("+1" in text or "+5" in text for text in button_texts)
        assert any("-1" in text or "-5" in text for text in button_texts)
        assert any("payment" in text.lower() or "Proceed" in text for text in button_texts)

    def test_validate_quantity(self, formatter):
        """Test quantity validation."""
        # Valid quantities
        assert formatter.validate_quantity(1, 10) == 1
        assert formatter.validate_quantity(5, 10) == 5
        assert formatter.validate_quantity(10, 10) == 10
        
        # Invalid - exceeds stock
        assert formatter.validate_quantity(15, 10) == 10  # Should cap at max
        
        # Invalid - below minimum
        assert formatter.validate_quantity(0, 10) == 1  # Should be at least 1
        assert formatter.validate_quantity(-5, 10) == 1  # Should be at least 1

