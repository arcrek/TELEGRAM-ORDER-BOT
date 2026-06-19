"""Verify /export buttons are wired into the keyboards."""
from unittest.mock import MagicMock

from src.bot.handlers.commands import _start_inline_keyboard
from src.bot.utils.keyboard import get_persistent_keyboard


def _fake_update():
    u = MagicMock()
    u.effective_user.language_code = "en"
    return u


def test_export_button_in_start_inline_keyboard():
    kb = _start_inline_keyboard(_fake_update())
    datas = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "start_export" in datas


def test_export_button_in_persistent_keyboard():
    kb = get_persistent_keyboard(_fake_update())
    texts = [b.text for row in kb.keyboard for b in row]
    assert any(("Export" in txt) or ("Xuất" in txt) for txt in texts)
