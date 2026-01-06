"""
Tests for supplier bot handlers.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, Message, User, Chat
from telegram.ext import ContextTypes
from src.bot_supplier.handlers.commands import start, register, help_command
from src.bot_supplier.handlers.messages import handle_supplier_reply, parse_product_data
from src.database.services.supplier_service import SupplierService


@pytest.fixture
def db_session():
    """Create a test database session."""
    # Use in-memory SQLite for isolation
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src.database.models.base import Base
    
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def mock_update():
    """Create a mock Telegram update."""
    user = User(
        id=123456789,
        first_name="Test",
        is_bot=False,
    )
    chat = Chat(id=123456789, type="private")
    message = Message(
        message_id=1,
        date=None,
        chat=chat,
        from_user=user,
    )
    update = Update(update_id=1, message=message)
    return update


@pytest.fixture
def mock_update_with_mock_message():
    """Create a mock Telegram update with mockable message."""
    update = MagicMock(spec=Update)
    update.update_id = 1
    update.effective_user = User(
        id=123456789,
        first_name="Test",
        is_bot=False,
    )
    update.message = MagicMock()
    update.message.chat = Chat(id=123456789, type="private")
    update.message.from_user = update.effective_user
    update.message.message_id = 1
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    """Create a mock context."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []
    context.bot_data = {}
    return context


class TestParseProductData:
    """Test product data parsing."""

    def test_parse_key_value_format(self):
        """Test parsing key:value format."""
        text = "username: user123\npassword: pass456"
        data = parse_product_data(text)
        
        assert data == {
            "username": "user123",
            "password": "pass456",
        }

    def test_parse_simple_text(self):
        """Test parsing simple text."""
        text = "This is a simple product code"
        data = parse_product_data(text)
        
        assert "data" in data
        assert data["data"] == "This is a simple product code"

    def test_parse_mixed_format(self):
        """Test parsing mixed format."""
        text = "username: user123\npassword: pass456\n\nAdditional notes here"
        data = parse_product_data(text)
        
        assert "username" in data
        assert "password" in data
        assert data["username"] == "user123"
        assert data["password"] == "pass456"

    def test_parse_empty_text(self):
        """Test parsing empty text."""
        data = parse_product_data("")
        assert data == {"data": ""}


class TestSupplierBotCommands:
    """Test supplier bot command handlers."""

    @pytest.mark.asyncio
    async def test_start_command(self, mock_update_with_mock_message, mock_context):
        """Test /start command."""
        await start(mock_update_with_mock_message, mock_context)
        
        mock_update_with_mock_message.message.reply_text.assert_called_once()
        call_args = mock_update_with_mock_message.message.reply_text.call_args[0][0]
        assert "Welcome to Supplier Bot" in call_args
        assert "/register" in call_args

    @pytest.mark.asyncio
    async def test_help_command(self, mock_update_with_mock_message, mock_context):
        """Test /help command."""
        await help_command(mock_update_with_mock_message, mock_context)
        
        mock_update_with_mock_message.message.reply_text.assert_called_once()
        call_args = mock_update_with_mock_message.message.reply_text.call_args[0][0]
        assert "/register" in call_args
        assert "Order Management" in call_args

    @pytest.mark.asyncio
    async def test_register_command_new_supplier(self, mock_update_with_mock_message, mock_context, db_session):
        """Test /register command for new supplier."""
        mock_context.args = []
        
        with patch("src.bot_supplier.handlers.commands.get_session_factory") as mock_factory:
            mock_factory.return_value = lambda: db_session
            
            await register(mock_update_with_mock_message, mock_context)
            
            mock_update_with_mock_message.message.reply_text.assert_called_once()
            call_args = mock_update_with_mock_message.message.reply_text.call_args[0][0]
            assert "Successfully registered" in call_args
            
            # Verify supplier was created
            supplier_service = SupplierService(db_session)
            supplier = supplier_service.get_supplier_by_telegram_id(123456789)
            assert supplier is not None

    @pytest.mark.asyncio
    async def test_register_command_existing_supplier(self, mock_update_with_mock_message, mock_context, db_session):
        """Test /register command for existing supplier."""
        # Create supplier first
        supplier_service = SupplierService(db_session)
        supplier = supplier_service.create_supplier(
            telegram_user_id=123456789,
            name="Existing Supplier",
            is_active=True,
        )
        
        mock_context.args = []
        
        with patch("src.bot_supplier.handlers.commands.get_session_factory") as mock_factory:
            mock_factory.return_value = lambda: db_session
            
            await register(mock_update_with_mock_message, mock_context)
            
            mock_update_with_mock_message.message.reply_text.assert_called_once()
            call_args = mock_update_with_mock_message.message.reply_text.call_args[0][0]
            assert "already registered" in call_args


class TestSupplierReplyHandler:
    """Test supplier reply handler."""

    @pytest.mark.asyncio
    async def test_handle_supplier_reply_not_registered(self, mock_update_with_mock_message, mock_context, db_session):
        """Test handling reply when supplier is not registered."""
        # Create reply message
        reply_to_message = Message(
            message_id=100,
            date=None,
            chat=Chat(id=123456789, type="private"),
            from_user=User(id=999999999, first_name="Bot", is_bot=True),
        )
        # Set reply_to_message and text on the mock message
        mock_update_with_mock_message.message.reply_to_message = reply_to_message
        mock_update_with_mock_message.message.text = "username: user123\npassword: pass456"
        mock_update_with_mock_message.message.message_id = 2
        
        with patch("src.bot_supplier.handlers.messages.get_session_factory") as mock_factory:
            mock_factory.return_value = lambda: db_session
            
            await handle_supplier_reply(mock_update_with_mock_message, mock_context)
            
            mock_update_with_mock_message.message.reply_text.assert_called_once()
            call_args = mock_update_with_mock_message.message.reply_text.call_args[0][0]
            assert "not registered" in call_args

    @pytest.mark.asyncio
    async def test_handle_supplier_reply_no_reply(self, mock_update_with_mock_message, mock_context):
        """Test handling message that is not a reply."""
        # Set reply_to_message to None
        mock_update_with_mock_message.message.reply_to_message = None
        
        with patch("src.bot_supplier.handlers.messages.get_session_factory"):
            await handle_supplier_reply(mock_update_with_mock_message, mock_context)
            
            # Should return early without sending message
            mock_update_with_mock_message.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_supplier_reply_invalid_order(self, mock_update_with_mock_message, mock_context, db_session):
        """Test handling reply to non-existent order."""
        # Create supplier
        supplier_service = SupplierService(db_session)
        supplier = supplier_service.create_supplier(
            telegram_user_id=123456789,
            name="Test Supplier",
        )
        
        # Create reply message with non-existent message ID
        reply_to_message = Message(
            message_id=999999,
            date=None,
            chat=Chat(id=123456789, type="private"),
            from_user=User(id=999999999, first_name="Bot", is_bot=True),
        )
        # Set reply_to_message and text on the mock message
        mock_update_with_mock_message.message.reply_to_message = reply_to_message
        mock_update_with_mock_message.message.text = "username: user123"
        mock_update_with_mock_message.message.message_id = 2
        
        with patch("src.bot_supplier.handlers.messages.get_session_factory") as mock_factory:
            mock_factory.return_value = lambda: db_session
            
            await handle_supplier_reply(mock_update_with_mock_message, mock_context)
            
            mock_update_with_mock_message.message.reply_text.assert_called_once()
            call_args = mock_update_with_mock_message.message.reply_text.call_args[0][0]
            assert "not associated" in call_args

