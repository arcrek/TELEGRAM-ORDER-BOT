"""
User preference service layer for managing user language preferences.
"""
import uuid

from sqlalchemy.orm import Session

from src.database.models.user_preference import UserPreference


class UserPreferenceService:
    """Service for user preference operations."""

    def __init__(self, session: Session):
        """
        Initialize user preference service.
        
        Args:
            session: Database session
        """
        self.session = session

    def get_user_language(self, telegram_user_id: int) -> str:
        """
        Get user's preferred language.
        
        Args:
            telegram_user_id: Telegram user ID
            
        Returns:
            Language code ('en' or 'vi'), defaults to 'vi'
        """
        preference = self.get_user_preference(telegram_user_id)
        if preference:
            return preference.language
        return "vi"  # Default language - Vietnamese

    def set_user_language(self, telegram_user_id: int, language: str) -> UserPreference:
        """
        Set user's preferred language.
        
        Args:
            telegram_user_id: Telegram user ID
            language: Language code ('en' or 'vi')
            
        Returns:
            UserPreference instance
        """
        # Validate language
        if language not in ["en", "vi"]:
            language = "vi"  # Default to Vietnamese
        
        preference = self.get_user_preference(telegram_user_id)
        
        if preference:
            preference.language = language
            self.session.commit()
            self.session.refresh(preference)
            return preference
        else:
            # Create new preference
            preference = UserPreference(
                id=str(uuid.uuid4()),
                telegram_user_id=telegram_user_id,
                language=language,
            )
            self.session.add(preference)
            self.session.commit()
            self.session.refresh(preference)
            return preference

    def get_user_preference(self, telegram_user_id: int) -> UserPreference | None:
        """
        Get user preference by Telegram user ID.
        
        Args:
            telegram_user_id: Telegram user ID
            
        Returns:
            UserPreference instance or None if not found
        """
        return self.session.query(UserPreference).filter_by(telegram_user_id=telegram_user_id).first()

