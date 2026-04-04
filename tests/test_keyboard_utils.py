"""
Tests for persistent keyboard utility.
"""
from unittest.mock import MagicMock, patch

from src.bot.utils.keyboard import get_persistent_keyboard


def _mock_update():
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    return update


@patch("src.bot.utils.keyboard.t")
@patch("src.bot.utils.keyboard._get_webapp_button_config")
def test_keyboard_without_webapp_button(mock_webapp_config, mock_t):
    mock_t.side_effect = lambda key, _update: "Products" if key == "buttons.products" else "Language"
    mock_webapp_config.return_value = (None, None)

    keyboard = get_persistent_keyboard(_mock_update())

    assert len(keyboard.keyboard) == 1
    assert keyboard.keyboard[0][0].text == "Products"
    assert keyboard.keyboard[0][1].text == "Language"


@patch("src.bot.utils.keyboard.t")
@patch("src.bot.utils.keyboard._get_webapp_button_config")
def test_keyboard_with_webapp_button(mock_webapp_config, mock_t):
    mock_t.side_effect = lambda key, _update: "Products" if key == "buttons.products" else "Language"
    mock_webapp_config.return_value = ("Open App", "https://example.com/app")

    keyboard = get_persistent_keyboard(_mock_update())

    assert len(keyboard.keyboard) == 2
    assert keyboard.keyboard[1][0].text == "Open App"
    assert keyboard.keyboard[1][0].web_app.url == "https://example.com/app"
