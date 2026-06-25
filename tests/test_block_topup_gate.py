"""A blocked user cannot create a topup via either preset or custom path."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models.base import Base
from src.database.models.bot_user import BotUser
from src.database.services.block_service import BlockService


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _seed_user(session_factory, telegram_id, username=None):
    s = session_factory()
    s.add(BotUser(telegram_user_id=telegram_id, username=username, has_started=True))
    s.commit()
    s.close()


def test_blocked_user_preset_topup_rejected(session_factory):
    from src.bot.handlers import balance

    _seed_user(session_factory, 600, "blockeduser")
    BlockService(session_factory()).block("600")

    query = MagicMock()
    query.data = "topup_amount_50000"
    query.from_user.id = 600
    query.from_user.username = "blockeduser"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.message.message_id = 1
    update = MagicMock()
    update.callback_query = query

    with (
        patch.object(balance, "get_session_factory", return_value=session_factory),
        patch(
            "src.database.services.topup_service.TopupService.create_topup"
        ) as create_topup,
        patch.object(balance, "_create_topup_qr", new=AsyncMock()),
    ):
        asyncio.run(balance.handle_balance_topup_amount(update, MagicMock()))

    create_topup.assert_not_called()
    query.edit_message_text.assert_awaited()


def test_blocked_user_custom_topup_rejected(session_factory):
    from src.bot.handlers import balance
    from src.bot.states.state_manager import UserState

    _seed_user(session_factory, 601)
    BlockService(session_factory()).block("601")

    update = MagicMock()
    update.message.text = "50000"
    update.message.reply_text = AsyncMock()
    update.effective_user.id = 601
    update.effective_user.username = None

    state = UserState()
    state.awaiting_topup_amount = True

    with (
        patch.object(balance, "get_session_factory", return_value=session_factory),
        patch.object(balance.state_manager, "get_user_state", return_value=state),
        patch.object(balance.state_manager, "set_user_state"),
        patch(
            "src.database.services.topup_service.TopupService.create_topup"
        ) as create_topup,
        patch.object(balance, "_create_topup_qr", new=AsyncMock()),
    ):
        asyncio.run(balance.handle_topup_amount_text(update, MagicMock()))

    create_topup.assert_not_called()
    update.message.reply_text.assert_awaited()
