"""
Language utility functions for bot handlers.
"""
from telegram import Update

from src.database.connection import get_session_factory
from src.database.services.user_preference_service import UserPreferenceService
from src.i18n.bot_translations import (
    DEFAULT_LANGUAGE,
    get_translation,
)


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
        # No user context; fall back to global default (Vietnamese)
        return DEFAULT_LANGUAGE

    try:
        session_factory = get_session_factory()
        session = session_factory()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"DB unavailable for language lookup: {e}")
        return DEFAULT_LANGUAGE

    try:
        preference_service = UserPreferenceService(session)

        # Check if user has an explicit preference stored
        user_pref = preference_service.get_user_preference(user.id)
        if user_pref and user_pref.language:
            # Explicitly chosen language (via /lang), respect it
            return user_pref.language

        # No stored preference yet → DEFAULT to Vietnamese (regardless of Telegram UI language)
        #
        # We still keep detect_language_from_telegram_user available for future use,
        # but here we enforce Vietnamese as the initial language until the user changes it.
        preference_service.set_user_language(user.id, DEFAULT_LANGUAGE)
        return DEFAULT_LANGUAGE
    except Exception:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception("Error getting user language")
        # Conservative fallback: use global default (Vietnamese)
        return DEFAULT_LANGUAGE
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

