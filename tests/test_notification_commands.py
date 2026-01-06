"""
Tests for notification command handlers.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, Message, User
from telegram.ext import ContextTypes
from src.bot.handlers.notification_commands import notify_all, notify_user, notify_active


@pytest.fixture
def mock_update():
    """Create a mock Telegram update."""
    update = Mock(spec=Update)
    update.effective_user = Mock(spec=User)
    update.effective_user.id = 123456789
    update.message = Mock(spec=Message)
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    """Create a mock bot context."""
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = Mock()
    context.bot.send_message = Mock()
    context.args = []
    return context


@pytest.fixture
def admin_update(mock_update):
    """Create an update from an admin user."""
    with patch('src.bot.handlers.notification_commands.is_admin', return_value=True):
        yield mock_update


@pytest.fixture
def non_admin_update(mock_update):
    """Create an update from a non-admin user."""
    with patch('src.bot.handlers.notification_commands.is_admin', return_value=False):
        yield mock_update


class TestNotificationCommands:
    """Test notification command handlers."""

    @pytest.mark.asyncio
    async def test_notify_all_non_admin(self, non_admin_update, mock_context):
        """Test that non-admin users cannot use notify_all."""
        await notify_all(non_admin_update, mock_context)
        
        non_admin_update.message.reply_text.assert_called_once()
        call_args = non_admin_update.message.reply_text.call_args[0][0]
        assert "administrators" in call_args.lower()

    @pytest.mark.asyncio
    async def test_notify_all_no_message(self, admin_update, mock_context):
        """Test notify_all without message."""
        mock_context.args = []
        
        await notify_all(admin_update, mock_context)
        
        admin_update.message.reply_text.assert_called_once()
        call_args = admin_update.message.reply_text.call_args[0][0]
        assert "Usage" in call_args

    @pytest.mark.asyncio
    async def test_notify_all_success(self, admin_update, mock_context):
        """Test successful notify_all command."""
        mock_context.args = ["Hello", "everyone!"]
        
        with patch('src.bot.handlers.notification_commands.get_session_factory') as mock_factory, \
             patch('src.bot.handlers.notification_commands.NotificationService') as mock_service_class:
            
            mock_session = Mock()
            mock_factory.return_value = Mock(return_value=mock_session)
            
            mock_service = Mock()
            mock_service.send_notification_to_all_started.return_value = {
                "total": 5,
                "success": 5,
                "failed": 0,
                "details": []
            }
            mock_service_class.return_value = mock_service
            
            await notify_all(admin_update, mock_context)
            
            # Should send notification and report results
            assert admin_update.message.reply_text.call_count >= 1
            call_args = admin_update.message.reply_text.call_args[0][0]
            assert "Notification sent" in call_args or "Statistics" in call_args

    @pytest.mark.asyncio
    async def test_notify_user_non_admin(self, non_admin_update, mock_context):
        """Test that non-admin users cannot use notify_user."""
        await notify_user(non_admin_update, mock_context)
        
        non_admin_update.message.reply_text.assert_called_once()
        call_args = non_admin_update.message.reply_text.call_args[0][0]
        assert "administrators" in call_args.lower()

    @pytest.mark.asyncio
    async def test_notify_user_insufficient_args(self, admin_update, mock_context):
        """Test notify_user with insufficient arguments."""
        mock_context.args = ["123456789"]  # Missing message
        
        await notify_user(admin_update, mock_context)
        
        admin_update.message.reply_text.assert_called_once()
        call_args = admin_update.message.reply_text.call_args[0][0]
        assert "Usage" in call_args

    @pytest.mark.asyncio
    async def test_notify_user_invalid_user_id(self, admin_update, mock_context):
        """Test notify_user with invalid user ID."""
        mock_context.args = ["invalid", "message"]
        
        await notify_user(admin_update, mock_context)
        
        admin_update.message.reply_text.assert_called_once()
        call_args = admin_update.message.reply_text.call_args[0][0]
        assert "Invalid user ID" in call_args

    @pytest.mark.asyncio
    async def test_notify_user_success(self, admin_update, mock_context):
        """Test successful notify_user command."""
        mock_context.args = ["123456789", "Hello", "user!"]
        
        with patch('src.bot.handlers.notification_commands.get_session_factory') as mock_factory, \
             patch('src.bot.handlers.notification_commands.NotificationService') as mock_service_class:
            
            mock_session = Mock()
            mock_factory.return_value = Mock(return_value=mock_session)
            
            mock_service = Mock()
            mock_service.send_notification_to_user.return_value = {
                "success": True,
                "telegram_user_id": 123456789
            }
            mock_service_class.return_value = mock_service
            
            await notify_user(admin_update, mock_context)
            
            # Should send notification and report success
            assert admin_update.message.reply_text.call_count >= 1
            call_args = admin_update.message.reply_text.call_args[0][0]
            assert "successfully" in call_args.lower()

    @pytest.mark.asyncio
    async def test_notify_active_non_admin(self, non_admin_update, mock_context):
        """Test that non-admin users cannot use notify_active."""
        await notify_active(non_admin_update, mock_context)
        
        non_admin_update.message.reply_text.assert_called_once()
        call_args = non_admin_update.message.reply_text.call_args[0][0]
        assert "administrators" in call_args.lower()

    @pytest.mark.asyncio
    async def test_notify_active_no_message(self, admin_update, mock_context):
        """Test notify_active without message."""
        mock_context.args = []
        
        await notify_active(admin_update, mock_context)
        
        admin_update.message.reply_text.assert_called_once()
        call_args = admin_update.message.reply_text.call_args[0][0]
        assert "Usage" in call_args

    @pytest.mark.asyncio
    async def test_notify_active_success(self, admin_update, mock_context):
        """Test successful notify_active command."""
        mock_context.args = ["Hello", "active", "users!"]
        
        with patch('src.bot.handlers.notification_commands.get_session_factory') as mock_factory, \
             patch('src.bot.handlers.notification_commands.NotificationService') as mock_service_class:
            
            mock_session = Mock()
            mock_factory.return_value = Mock(return_value=mock_session)
            
            mock_service = Mock()
            mock_service.send_notification_to_active_users.return_value = {
                "total": 3,
                "success": 3,
                "failed": 0,
                "details": []
            }
            mock_service_class.return_value = mock_service
            
            await notify_active(admin_update, mock_context)
            
            # Should send notification and report results
            assert admin_update.message.reply_text.call_count >= 1
            call_args = admin_update.message.reply_text.call_args[0][0]
            assert "active users" in call_args.lower() or "Statistics" in call_args

