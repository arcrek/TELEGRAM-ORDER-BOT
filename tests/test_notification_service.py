"""
Tests for notification service.
Following TDD: Write tests first, then implement service.
"""
import asyncio
import pytest
from unittest.mock import Mock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models.base import Base
from src.database.services.notification_service import NotificationService
from src.database.services.bot_user_service import BotUserService
from telegram.error import BadRequest


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
def mock_bot():
    """Create a mock Telegram bot."""
    bot = Mock()
    bot.send_message = Mock()
    bot.send_photo = Mock(return_value=Mock(photo=[Mock(file_id="FILEID_FIRST")]))
    return bot


@pytest.fixture
def notification_service(db_session, mock_bot):
    """Create notification service instance."""
    return NotificationService(db_session, bot=mock_bot)


@pytest.fixture
def sample_users(db_session):
    """Create sample bot users for testing."""
    bot_user_service = BotUserService(db_session)
    
    user1 = bot_user_service.track_user(
        telegram_user_id=111,
        username="user1",
        first_name="User",
        last_name="1",
    )
    user2 = bot_user_service.track_user(
        telegram_user_id=222,
        username="user2",
        first_name="User",
        last_name="2",
    )
    user3 = bot_user_service.track_user(
        telegram_user_id=333,
        username="user3",
        first_name="User",
        last_name="3",
    )
    
    # Make user3 inactive
    bot_user_service.update_user_active_status(333, False)
    
    return [user1, user2, user3]


class TestNotificationService:
    """Test NotificationService class."""

    def test_send_notification_to_user_success(self, notification_service, mock_bot):
        """Test successfully sending notification to a user."""
        mock_bot.send_message.return_value = Mock(message_id=123)
        
        result = notification_service.send_notification_to_user(
            telegram_user_id=123456789,
            message="Test notification"
        )
        
        assert result["success"] is True
        assert result["telegram_user_id"] == 123456789
        mock_bot.send_message.assert_called_once_with(
            chat_id=123456789,
            text="Test notification"
        )

    def test_send_notification_to_user_telegram_error(self, notification_service, mock_bot):
        """Test handling Telegram error when sending notification."""
        mock_bot.send_message.side_effect = BadRequest("User blocked the bot")
        
        result = notification_service.send_notification_to_user(
            telegram_user_id=123456789,
            message="Test notification"
        )
        
        assert result["success"] is False
        assert "error" in result
        assert result["telegram_user_id"] == 123456789

    def test_send_notification_to_user_no_bot(self, db_session):
        """Test sending notification without bot instance."""
        service = NotificationService(db_session, bot=None)
        
        result = service.send_notification_to_user(
            telegram_user_id=123456789,
            message="Test notification"
        )
        
        assert result["success"] is False
        assert "Bot instance not available" in result["error"]

    def test_send_notification_to_all_started(self, notification_service, mock_bot, sample_users):
        """Test sending notification to all started users."""
        mock_bot.send_message.return_value = Mock(message_id=123)
        
        result = notification_service.send_notification_to_all_started("Test broadcast")
        
        assert result["total"] == 3  # All 3 users have started
        assert result["success"] == 3
        assert result["failed"] == 0
        assert len(result["details"]) == 3
        assert mock_bot.send_message.call_count == 3

    def test_send_notification_to_active_users(self, notification_service, mock_bot, sample_users):
        """Test sending notification to active users only."""
        mock_bot.send_message.return_value = Mock(message_id=123)
        
        result = notification_service.send_notification_to_active_users("Test to active")
        
        assert result["total"] == 2  # Only 2 active users
        assert result["success"] == 2
        assert result["failed"] == 0
        assert len(result["details"]) == 2
        assert mock_bot.send_message.call_count == 2

    def test_send_notification_to_multiple_users(self, notification_service, mock_bot):
        """Test sending notification to multiple specific users."""
        mock_bot.send_message.return_value = Mock(message_id=123)
        
        user_ids = [111, 222, 333]
        result = notification_service.send_notification_to_multiple_users(
            telegram_user_ids=user_ids,
            message="Test to multiple"
        )
        
        assert result["total"] == 3
        assert result["success"] == 3
        assert result["failed"] == 0
        assert len(result["details"]) == 3
        assert mock_bot.send_message.call_count == 3

    def test_send_notification_partial_failure(self, notification_service, mock_bot):
        """Test handling partial failures when sending to multiple users."""
        def side_effect(chat_id, text):
            if chat_id == 222:
                raise BadRequest("User blocked the bot")
            return Mock(message_id=123)
        
        mock_bot.send_message.side_effect = side_effect
        
        user_ids = [111, 222, 333]
        result = notification_service.send_notification_to_multiple_users(
            telegram_user_ids=user_ids,
            message="Test with failures"
        )
        
        assert result["total"] == 3
        assert result["success"] == 2
        assert result["failed"] == 1
        assert len(result["details"]) == 3
        
        # Check that success details are correct
        success_results = [r for r in result["details"] if r["success"]]
        failed_results = [r for r in result["details"] if not r["success"]]
        assert len(success_results) == 2
        assert len(failed_results) == 1
        assert failed_results[0]["telegram_user_id"] == 222


class TestNotificationServiceImage:
    """Image-attachment behavior for broadcasts."""

    def test_text_only_path_unchanged(self, notification_service, mock_bot):
        """No image -> uses send_message, never send_photo."""
        mock_bot.send_message.return_value = Mock(message_id=1)
        result = notification_service.send_notification_to_user(
            telegram_user_id=111, message="hello"
        )
        assert result["success"] is True
        mock_bot.send_message.assert_called_once_with(chat_id=111, text="hello")
        mock_bot.send_photo.assert_not_called()

    def test_image_short_text_uses_caption(self, notification_service, mock_bot):
        """Image + short text -> single send_photo with caption."""
        res = asyncio.run(
            notification_service.send_notification_to_user_async(
                telegram_user_id=111, message="cap", image_bytes=b"PNGBYTES"
            )
        )
        assert res["success"] is True
        assert mock_bot.send_photo.call_count == 1
        _, kwargs = mock_bot.send_photo.call_args
        assert kwargs["chat_id"] == 111
        assert kwargs["caption"] == "cap"
        mock_bot.send_message.assert_not_called()

    def test_image_long_text_sends_photo_then_message(self, notification_service, mock_bot):
        """Image + text > 1024 chars -> send_photo (no caption) then send_message."""
        long_text = "x" * 1100
        mock_bot.send_message.return_value = Mock(message_id=2)
        res = asyncio.run(
            notification_service.send_notification_to_user_async(
                telegram_user_id=111, message=long_text, image_bytes=b"PNGBYTES"
            )
        )
        assert res["success"] is True
        _, photo_kwargs = mock_bot.send_photo.call_args
        assert photo_kwargs.get("caption") is None
        mock_bot.send_message.assert_called_once_with(chat_id=111, text=long_text)

    def test_image_only_no_caption(self, notification_service, mock_bot):
        """Image, empty text -> send_photo with caption=None, no send_message."""
        res = asyncio.run(
            notification_service.send_notification_to_user_async(
                telegram_user_id=111, message="", image_bytes=b"PNGBYTES"
            )
        )
        assert res["success"] is True
        _, kwargs = mock_bot.send_photo.call_args
        assert kwargs.get("caption") is None
        mock_bot.send_message.assert_not_called()

    def test_broadcast_reuses_file_id_after_first_send(self, notification_service, mock_bot, sample_users):
        """First recipient uploads bytes; later recipients get the captured file_id string."""
        res = notification_service.send_notification_to_all_started(
            "cap", image_bytes=b"PNGBYTES"
        )
        assert res["total"] == 3
        assert res["success"] == 3
        assert mock_bot.send_photo.call_count == 3
        photos = [c.kwargs["photo"] for c in mock_bot.send_photo.call_args_list]
        # First send wraps bytes (not a str); subsequent sends reuse the file_id string.
        assert not isinstance(photos[0], str)
        assert photos[1] == "FILEID_FIRST"
        assert photos[2] == "FILEID_FIRST"

    def test_broadcast_first_send_fails_keeps_using_bytes(self, notification_service, mock_bot, sample_users):
        """If the first recipient fails, no file_id is captured, so the next still uploads bytes."""
        from telegram.error import BadRequest
        calls = {"n": 0}

        def photo_side_effect(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise BadRequest("blocked")
            return Mock(photo=[Mock(file_id="FILEID_SECOND")])

        mock_bot.send_photo.side_effect = photo_side_effect
        res = notification_service.send_notification_to_all_started(
            "cap", image_bytes=b"PNGBYTES"
        )
        assert res["failed"] == 1
        assert res["success"] == 2
        photos = [c.kwargs["photo"] for c in mock_bot.send_photo.call_args_list]
        assert not isinstance(photos[0], str)   # first: bytes (failed)
        assert not isinstance(photos[1], str)   # second: bytes again (no file_id yet)
        assert photos[2] == "FILEID_SECOND"     # third: reuse captured id

