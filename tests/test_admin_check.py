from unittest.mock import MagicMock

import pytest

from src.bot.utils import admin_check


def test_configured_owner_is_admin(monkeypatch):
    monkeypatch.setenv("BOT_OWNER_TELEGRAM_ID", "123456")
    monkeypatch.setattr(admin_check, "_get_session", MagicMock())
    monkeypatch.setattr(
        admin_check,
        "_database_admin_ids",
        lambda: [222],
        raising=False,
    )
    assert admin_check.get_owner_telegram_id() == 123456
    assert admin_check.is_owner(123456) is True
    assert admin_check.is_admin(123456) is True


@pytest.mark.parametrize("raw", ["not-a-number", "0", "-1"])
def test_missing_or_invalid_owner_fails_closed(monkeypatch, raw):
    monkeypatch.delenv("BOT_OWNER_TELEGRAM_ID", raising=False)
    assert admin_check.get_owner_telegram_id() is None
    monkeypatch.setenv("BOT_OWNER_TELEGRAM_ID", raw)
    assert admin_check.get_owner_telegram_id() is None


def test_database_admins_remain_authorized_without_owner(monkeypatch):
    monkeypatch.delenv("BOT_OWNER_TELEGRAM_ID", raising=False)
    monkeypatch.setattr(
        admin_check,
        "_database_admin_ids",
        lambda: [222],
        raising=False,
    )
    assert admin_check.get_admin_telegram_ids() == [222]
    assert admin_check.is_admin(222) is True


def test_owner_cannot_be_removed(monkeypatch):
    monkeypatch.setenv("BOT_OWNER_TELEGRAM_ID", "123456")
    session = MagicMock()
    monkeypatch.setattr(admin_check, "_get_session", lambda: session)
    monkeypatch.setattr(
        "src.database.services.bot_admin_service.BotAdminService",
        lambda _session: MagicMock(remove=MagicMock(return_value=True)),
    )
    assert admin_check.remove_admin(123456) is False
