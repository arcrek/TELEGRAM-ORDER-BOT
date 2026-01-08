"""
Language utility functions for bot handlers.
"""
from telegram import Update
from src.database.connection import get_session_factory
from src.database.services.user_preference_service import UserPreferenceService
from src.i18n.bot_translations import detect_language_from_telegram_user, get_translation


def get_user_language(update: Update) -> str:
    """
    Get user's preferred language from database or detect from Telegram user.
    
    Args:
        update: Telegram update object
        
    Returns:
        Language code ('en' or 'vi')
    """
    user = update.effective_user
    if not user:
        return "vi"  # Default to Vietnamese
    
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        preference_service = UserPreferenceService(session)
        language = preference_service.get_user_language(user.id)
        
        # If no preference exists, detect from Telegram and save it
        if language == "vi" and not preference_service.get_user_preference(user.id):
            detected_lang = detect_language_from_telegram_user(user)
            preference_service.set_user_language(user.id, detected_lang)
            return detected_lang
        
        return language
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting user language: {e}", exc_info=True)
        # Fallback to detection
        return detect_language_from_telegram_user(user)
    finally:
        session.close()


def t(key: str, update: Update, **kwargs) -> str:
    """
    Get translated string for a user.
    
    Args:
        key: Translation key in dot notation
        update: Telegram update object
        **kwargs: Variables to format into the translation string
        
    Returns:
        Translated string
    """
    language = get_user_language(update)
    return get_translation(key, language, **kwargs)

