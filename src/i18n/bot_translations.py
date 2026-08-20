"""
Translation utilities for Telegram bot.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Default language - Vietnamese for Vietnam market
DEFAULT_LANGUAGE = "vi"

# Supported languages
SUPPORTED_LANGUAGES = ["en", "vi"]

# Translation cache
_translation_cache: dict[str, dict] = {}


def _load_translations(language: str) -> dict:
    """
    Load translations for a specific language.
    
    Args:
        language: Language code (e.g., 'en', 'vi')
        
    Returns:
        Dictionary of translations
    """
    if language in _translation_cache:
        return _translation_cache[language]
    
    # Get the directory of this file
    current_dir = Path(__file__).parent
    translation_file = current_dir / "locales" / language / "bot.json"
    
    if not translation_file.exists():
        logger.warning(f"Translation file not found: {translation_file}")
        # Fallback to English if file doesn't exist
        if language != DEFAULT_LANGUAGE:
            return _load_translations(DEFAULT_LANGUAGE)
        return {}
    
    try:
        with open(translation_file, "r", encoding="utf-8") as f:
            translations = json.load(f)
            _translation_cache[language] = translations
            return translations
    except Exception as e:
        logger.error(f"Error loading translations for {language}: {e}")
        # Fallback to English
        if language != DEFAULT_LANGUAGE:
            return _load_translations(DEFAULT_LANGUAGE)
        return {}


def get_translation(key: str, language: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """
    Get a translated string by key.
    
    Args:
        key: Translation key in dot notation (e.g., 'commands.start.welcome')
        language: Language code (default: 'en')
        **kwargs: Variables to format into the translation string
        
    Returns:
        Translated string, or the key if translation not found
    """
    if language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE
    
    translations = _load_translations(language)
    
    # Navigate through nested dictionary using dot notation
    keys = key.split(".")
    value = translations
    
    try:
        for k in keys:
            value = value[k]
        
        # Format the string if kwargs provided
        if kwargs and isinstance(value, str):
            try:
                return value.format(**kwargs)
            except KeyError as e:
                logger.warning(f"Missing format variable {e} in translation key {key}")
                return value
        
        return str(value) if value is not None else key
    except (KeyError, TypeError):
        # Fallback to English if key not found
        if language != DEFAULT_LANGUAGE:
            logger.debug(f"Translation key '{key}' not found in {language}, falling back to {DEFAULT_LANGUAGE}")
            return get_translation(key, DEFAULT_LANGUAGE, **kwargs)
        
        # If still not found, log and return key
        logger.warning(f"Translation key '{key}' not found in any language")
        return key


def detect_language_from_telegram_user(user) -> str:
    """
    Detect language from Telegram user's language code.
    
    Args:
        user: Telegram user object
        
    Returns:
        Language code ('en' or 'vi')
    """
    if hasattr(user, 'language_code') and user.language_code:
        lang_code = user.language_code.lower()
        # Check if English (en, en-US, en-GB, etc.)
        if lang_code.startswith('en'):
            return 'en'
        # Default to Vietnamese for all other languages (primary market)
        return 'vi'
    
    # Default to Vietnamese
    return DEFAULT_LANGUAGE

