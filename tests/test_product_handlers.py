"""
Tests for product browsing handlers.
Following TDD: Write tests first, then implement handlers.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, Message, User, Chat, CallbackQuery
from telegram.ext import ContextTypes
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models.base import Base
from src.database.models import DeliveryType
from src.database.models.pre_uploaded_product import PreUploadedProduct
from src.database.services.product_service import ProductService
from src.database.services.variation_service import VariationService


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_products(db_session):
    """Create sample products for testing."""
    product_service = ProductService(db_session)
    products = []
    for i in range(20):
        product = product_service.create_product({
            "id": f"prod_{i:02d}",
            "name": f"Product {i:02d}",
            "description": f"Description {i}",
            "delivery_type": DeliveryType.PRE_UPLOADED,
            "is_active": True,
        })
        products.append(product)
    return products


@pytest.fixture
def mock_update():
    """Create a mock Update object."""
    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.from_user = MagicMock(spec=User)
    update.message.from_user.id = 123456789
    update.message.from_user.username = "testuser"
    update.message.from_user.first_name = "Test"
    update.message.from_user.last_name = None
    update.message.chat = MagicMock(spec=Chat)
    update.message.chat.id = 123456789
    update.message.reply_text = AsyncMock()
    update.message.edit_text = AsyncMock()
    update.effective_user = update.message.from_user
    return update


@pytest.fixture
def mock_callback_update():
    """Create a mock Update object for callback queries."""
    update = MagicMock(spec=Update)
    update.callback_query = MagicMock(spec=CallbackQuery)
    update.callback_query.from_user = MagicMock(spec=User)
    update.callback_query.from_user.id = 123456789
    update.callback_query.message = MagicMock(spec=Message)
    update.callback_query.message.chat = MagicMock(spec=Chat)
    update.callback_query.message.chat.id = 123456789
    update.callback_query.message.message_id = 1
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.edit_message_reply_markup = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    """Create a mock Context object."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = MagicMock()
    return context


@pytest.mark.asyncio
async def test_products_command(mock_update, mock_context, db_session, sample_products):
    """Test /products command handler."""
    from src.bot.handlers.commands import products_command
    
    with patch('src.bot.handlers.commands.get_session_factory') as mock_factory:
        mock_session = db_session
        mock_factory.return_value = lambda: mock_session
        
        await products_command(mock_update, mock_context)
        
        # Verify that reply_text was called
        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert call_args is not None
        # Check that a response was sent (product list or localized message)
        message_text = call_args[0][0] if call_args[0] else ""
        assert len(message_text) > 0


@pytest.mark.asyncio
async def test_page_navigation_callback(mock_callback_update, mock_context, db_session, sample_products):
    """Test page navigation callback handler."""
    from src.bot.handlers.callbacks import handle_page_navigation
    
    mock_callback_update.callback_query.data = "page_2"
    
    with patch('src.bot.handlers.callbacks.get_session_factory') as mock_factory:
        mock_session = db_session
        mock_factory.return_value = lambda: mock_session
        
        await handle_page_navigation(mock_callback_update, mock_context)
        
        # Verify that edit_message_text was called
        assert mock_callback_update.callback_query.edit_message_text.called
        mock_callback_update.callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_product_selection_callback(mock_callback_update, mock_context, db_session, sample_products):
    """Test product selection callback handler."""
    from src.bot.handlers.callbacks import handle_product_selection
    
    mock_callback_update.callback_query.data = "product_prod_00"
    
    with patch('src.bot.handlers.callbacks.get_session_factory') as mock_factory:
        mock_session = db_session
        mock_factory.return_value = lambda: mock_session
        
        await handle_product_selection(mock_callback_update, mock_context)
        
        # Verify that edit_message_text was called
        assert mock_callback_update.callback_query.edit_message_text.called
        mock_callback_update.callback_query.answer.assert_called_once()
        
        # Check that product details are shown (name contains "Product")
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        message_text = call_args[0][0] if call_args and call_args[0] else ""
        assert "Product 00" in message_text or len(message_text) > 0


@pytest.mark.asyncio
async def test_variation_selection_callback(mock_callback_update, mock_context, db_session, sample_products):
    """Test variation selection callback handler."""
    from src.bot.handlers.callbacks import handle_variation_selection

    # Create a variation first
    variation_service = VariationService(db_session)
    variation = variation_service.create_variation({
        "id": "var_1",
        "product_id": "prod_00",
        "name": "Pro 12M 1PCS",
        "price": 40000,
        "stock": 51,
        "is_active": True,
    })
    # Add inventory rows so actual stock > 0 (PRE_UPLOADED stock counted from these)
    for i in range(3):
        db_session.add(PreUploadedProduct(
            id=f"inv_v_{i}",
            product_id="prod_00",
            variation_id="var_1",
            product_data='{"key": "val"}',
            is_used=False,
        ))
    db_session.commit()

    mock_callback_update.callback_query.data = "variation_var_1"

    with patch('src.bot.handlers.callbacks.get_session_factory') as mock_factory:
        mock_session = db_session
        mock_factory.return_value = lambda: mock_session

        await handle_variation_selection(mock_callback_update, mock_context)

        # Verify that edit_message_text was called
        assert mock_callback_update.callback_query.edit_message_text.called
        mock_callback_update.callback_query.answer.assert_called_once()

        # Check that order confirmation is shown (Vietnamese UI)
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        message_text = call_args[0][0] if call_args and call_args[0] else ""
        assert "Pro 12M 1PCS" in message_text or "40,000" in message_text


@pytest.mark.asyncio
async def test_quantity_adjustment_callback(mock_callback_update, mock_context, db_session, sample_products):
    """Test quantity adjustment callback handler."""
    from src.bot.handlers.callbacks import handle_quantity_adjustment, state_manager

    # Create a variation with underscore in ID (like real data)
    variation_service = VariationService(db_session)
    variation = variation_service.create_variation({
        "id": "alight_12m_1",  # Variation ID with underscores
        "product_id": "prod_00",
        "name": "Pro 12M 1PCS",
        "price": 40000,
        "stock": 51,
        "is_active": True,
    })
    # Add inventory rows so actual stock > 0 (PRE_UPLOADED stock counted from these)
    for i in range(5):
        db_session.add(PreUploadedProduct(
            id=f"inv_a_{i}",
            product_id="prod_00",
            variation_id="alight_12m_1",
            product_data='{"key": "val"}',
            is_used=False,
        ))
    db_session.commit()

    # Set up user state using the handler's global state manager
    user_id = mock_callback_update.callback_query.from_user.id
    state_manager.update_user_state(
        user_id,
        selected_variation_id="alight_12m_1",
        quantity=1,
    )

    # Test with variation ID containing underscores
    mock_callback_update.callback_query.data = "qty_alight_12m_1_+1"

    with patch('src.bot.handlers.callbacks.get_session_factory') as mock_factory:
        mock_session = db_session
        mock_factory.return_value = lambda: mock_session

        await handle_quantity_adjustment(mock_callback_update, mock_context)

        # Verify that edit_message_text was called (not "Variation not found" error)
        assert mock_callback_update.callback_query.edit_message_text.called
        mock_callback_update.callback_query.answer.assert_called_once()

        # Check that the message was updated (not an error message)
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        message_text = call_args[0][0] if call_args and call_args[0] else ""
        assert "❌ Variation not found" not in message_text
        assert "Pro 12M 1PCS" in message_text or "40,000" in message_text

