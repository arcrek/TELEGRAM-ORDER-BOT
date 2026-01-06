"""
Tests for bot user service.
Following TDD: Write tests first, then implement service.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models.base import Base
from src.database.services.bot_user_service import BotUserService


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
def bot_user_service(db_session):
    """Create bot user service instance."""
    return BotUserService(db_session)


class TestBotUserService:
    """Test BotUserService class."""

    def test_track_user_new_user(self, bot_user_service):
        """Test tracking a new user."""
        telegram_user_id = 123456789
        username = "testuser"
        first_name = "Test"
        last_name = "User"
        
        user = bot_user_service.track_user(
            telegram_user_id=telegram_user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        
        assert user is not None
        assert user.telegram_user_id == telegram_user_id
        assert user.username == username
        assert user.first_name == first_name
        assert user.last_name == last_name
        assert user.has_started is True
        assert user.started_at is not None
        assert user.is_active is True

    def test_track_user_existing_user(self, bot_user_service):
        """Test tracking an existing user updates information."""
        telegram_user_id = 123456789
        
        # Create user first
        user1 = bot_user_service.track_user(
            telegram_user_id=telegram_user_id,
            username="oldusername",
            first_name="Old",
            last_name="Name",
        )
        original_started_at = user1.started_at
        
        # Track again with updated info
        user2 = bot_user_service.track_user(
            telegram_user_id=telegram_user_id,
            username="newusername",
            first_name="New",
            last_name="Name",
        )
        
        assert user2.id == user1.id  # Same user
        assert user2.username == "newusername"
        assert user2.first_name == "New"
        assert user2.last_name == "Name"
        assert user2.has_started is True
        assert user2.started_at == original_started_at  # Should not change

    def test_track_user_sets_started_at_on_first_start(self, bot_user_service):
        """Test that started_at is set only on first /start."""
        telegram_user_id = 123456789
        
        user1 = bot_user_service.track_user(
            telegram_user_id=telegram_user_id,
            username="testuser",
            first_name="Test",
            last_name="User",
        )
        first_started_at = user1.started_at
        
        # Track again - started_at should remain the same
        user2 = bot_user_service.track_user(
            telegram_user_id=telegram_user_id,
            username="testuser",
            first_name="Test",
            last_name="User",
        )
        
        assert user2.started_at == first_started_at

    def test_get_user_by_telegram_id(self, bot_user_service):
        """Test getting user by Telegram ID."""
        telegram_user_id = 123456789
        
        created_user = bot_user_service.track_user(
            telegram_user_id=telegram_user_id,
            username="testuser",
            first_name="Test",
            last_name="User",
        )
        
        retrieved_user = bot_user_service.get_user_by_telegram_id(telegram_user_id)
        
        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.telegram_user_id == telegram_user_id

    def test_get_user_by_telegram_id_not_found(self, bot_user_service):
        """Test getting non-existent user."""
        assert bot_user_service.get_user_by_telegram_id(999999999) is None

    def test_get_all_started_users(self, bot_user_service):
        """Test getting all users who pressed /start."""
        # Create multiple users
        bot_user_service.track_user(telegram_user_id=111, username="user1", first_name="User", last_name="1")
        bot_user_service.track_user(telegram_user_id=222, username="user2", first_name="User", last_name="2")
        bot_user_service.track_user(telegram_user_id=333, username="user3", first_name="User", last_name="3")
        
        users = bot_user_service.get_all_started_users()
        
        assert len(users) == 3
        assert all(user.has_started is True for user in users)

    def test_get_active_users(self, bot_user_service):
        """Test getting only active users."""
        # Create active users
        bot_user_service.track_user(telegram_user_id=111, username="user1", first_name="User", last_name="1")
        bot_user_service.track_user(telegram_user_id=222, username="user2", first_name="User", last_name="2")
        
        # Create inactive user
        user3 = bot_user_service.track_user(telegram_user_id=333, username="user3", first_name="User", last_name="3")
        bot_user_service.update_user_active_status(user3.telegram_user_id, False)
        
        active_users = bot_user_service.get_active_users()
        
        assert len(active_users) == 2
        assert all(user.is_active is True for user in active_users)
        assert all(user.telegram_user_id in [111, 222] for user in active_users)

    def test_update_user_active_status(self, bot_user_service):
        """Test updating user active status."""
        user = bot_user_service.track_user(
            telegram_user_id=123456789,
            username="testuser",
            first_name="Test",
            last_name="User",
        )
        
        assert user.is_active is True
        
        updated_user = bot_user_service.update_user_active_status(user.telegram_user_id, False)
        
        assert updated_user is not None
        assert updated_user.is_active is False
        
        # Update back to active
        updated_user = bot_user_service.update_user_active_status(user.telegram_user_id, True)
        assert updated_user.is_active is True

    def test_update_user_active_status_not_found(self, bot_user_service):
        """Test updating active status for non-existent user."""
        assert bot_user_service.update_user_active_status(999999999, False) is None

    def test_update_user_info(self, bot_user_service):
        """Test updating user information."""
        user = bot_user_service.track_user(
            telegram_user_id=123456789,
            username="oldusername",
            first_name="Old",
            last_name="Name",
        )
        
        updated_user = bot_user_service.update_user_info(
            telegram_user_id=user.telegram_user_id,
            username="newusername",
            first_name="New",
            last_name="Name",
        )
        
        assert updated_user is not None
        assert updated_user.username == "newusername"
        assert updated_user.first_name == "New"
        assert updated_user.last_name == "Name"

    def test_update_user_info_not_found(self, bot_user_service):
        """Test updating info for non-existent user."""
        assert bot_user_service.update_user_info(
            telegram_user_id=999999999,
            username="test",
            first_name="Test",
            last_name="User",
        ) is None

