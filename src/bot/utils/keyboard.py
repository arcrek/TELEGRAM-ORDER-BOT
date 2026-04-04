"""
Keyboard utility functions for persistent keyboards.
"""
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from src.database.connection import get_session_factory
from src.database.services.bot_ui_settings_service import BotUiSettingsService
from src.bot.utils.language import t


def _get_webapp_button_config() -> tuple[str | None, str | None]:
    """Get optional web app button config from global bot UI settings."""
    session_factory = get_session_factory()
    session = session_factory()
    try:
        service = BotUiSettingsService(session)
        settings = service.get_settings()
        return settings.webapp_button_text, settings.webapp_url
    except Exception:
        return None, None
    finally:
        session.close()


def _is_valid_webapp_url(url: str | None) -> bool:
    if not url:
        return False
    lowered = url.lower()
    return lowered.startswith("https://") or lowered.startswith("http://")


def get_persistent_keyboard(update: Update) -> ReplyKeyboardMarkup:
    """
    Get the persistent keyboard with Products button.
    
    Args:
        update: Telegram update object
        
    Returns:
        ReplyKeyboardMarkup with persistent buttons
    """
    products_text = t("buttons.products", update)
    language_text = t("buttons.language", update)
    webapp_button_text, webapp_url = _get_webapp_button_config()
    
    keyboard = [
        [KeyboardButton(products_text), KeyboardButton(language_text)]
    ]

    if webapp_button_text and _is_valid_webapp_url(webapp_url):
        keyboard.append(
            [
                KeyboardButton(
                    webapp_button_text,
                    web_app=WebAppInfo(url=webapp_url),
                )
            ]
        )
    
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )
