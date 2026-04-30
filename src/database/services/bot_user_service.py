"""
Bot user service layer for user tracking.
"""
import uuid
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy import func
from sqlalchemy.orm import Session
from src.database.models.bot_user import BotUser


class BotUserService:
    """Service for bot user operations."""

    def __init__(self, session: Session):
        """
        Initialize bot user service.
        
        Args:
            session: Database session
        """
        self.session = session

    def generate_user_id(self) -> str:
        """
        Generate a unique user ID.
        
        Returns:
            User ID string
        """
        return str(uuid.uuid4())

    def track_user(
        self,
        telegram_user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> BotUser:
        """
        Track a user (create or update).
        Sets has_started to True and records started_at on first /start.
        
        Args:
            telegram_user_id: Telegram user ID
            username: Telegram username (optional)
            first_name: User's first name (optional)
            last_name: User's last name (optional)
        
        Returns:
            BotUser instance
        """
        # Check if user already exists
        existing_user = self.get_user_by_telegram_id(telegram_user_id)
        
        if existing_user:
            # Update user information
            if username is not None:
                existing_user.username = username
            if first_name is not None:
                existing_user.first_name = first_name
            if last_name is not None:
                existing_user.last_name = last_name
            
            # Update has_started if not already set
            if not existing_user.has_started:
                existing_user.has_started = True
                existing_user.started_at = datetime.now(timezone.utc)
            
            existing_user.is_active = True  # Mark as active on /start
            self.session.commit()
            self.session.refresh(existing_user)
            return existing_user
        else:
            # Create new user
            user = BotUser(
                id=self.generate_user_id(),
                telegram_user_id=telegram_user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                has_started=True,
                started_at=datetime.now(timezone.utc),
                is_active=True,
            )
            self.session.add(user)
            self.session.commit()
            self.session.refresh(user)
            return user

    def get_user_by_username(self, username: str) -> Optional[BotUser]:
        """
        Get user by Telegram username (case-insensitive, with or without @).

        Args:
            username: Telegram username (with or without leading @)

        Returns:
            BotUser instance or None if not found
        """
        username_clean = username.lstrip("@").lower()
        return (
            self.session.query(BotUser)
            .filter(func.lower(BotUser.username) == username_clean)
            .first()
        )

    def get_user_by_telegram_id(self, telegram_user_id: int) -> Optional[BotUser]:
        """
        Get user by Telegram user ID.
        
        Args:
            telegram_user_id: Telegram user ID
        
        Returns:
            BotUser instance or None if not found
        """
        return self.session.query(BotUser).filter_by(telegram_user_id=telegram_user_id).first()

    def get_all_started_users(self) -> List[BotUser]:
        """
        Get all users who have pressed /start.
        
        Returns:
            List of BotUser instances
        """
        return self.session.query(BotUser).filter_by(has_started=True).all()

    def get_active_users(self) -> List[BotUser]:
        """
        Get all active users.
        
        Returns:
            List of active BotUser instances
        """
        return self.session.query(BotUser).filter_by(is_active=True, has_started=True).all()

    def update_user_active_status(self, telegram_user_id: int, is_active: bool) -> Optional[BotUser]:
        """
        Update user active status.
        
        Args:
            telegram_user_id: Telegram user ID
            is_active: Active status
        
        Returns:
            Updated BotUser instance or None if not found
        """
        user = self.get_user_by_telegram_id(telegram_user_id)
        if not user:
            return None
        
        user.is_active = is_active
        self.session.commit()
        self.session.refresh(user)
        return user

    def update_user_info(
        self,
        telegram_user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> Optional[BotUser]:
        """
        Update user information.
        
        Args:
            telegram_user_id: Telegram user ID
            username: Telegram username (optional)
            first_name: User's first name (optional)
            last_name: User's last name (optional)
        
        Returns:
            Updated BotUser instance or None if not found
        """
        user = self.get_user_by_telegram_id(telegram_user_id)
        if not user:
            return None
        
        if username is not None:
            user.username = username
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        
        self.session.commit()
        self.session.refresh(user)
        return user

