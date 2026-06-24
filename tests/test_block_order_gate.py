"""A blocked user is rejected at the bot payment step before an order is created."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models.base import Base
from src.database.services.block_service import BlockService
from src.i18n.bot_translations import get_translation


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_blocked_user_cannot_create_order(session_factory):
    from src.bot.handlers import callbacks

    # Block user 500 by id.
    BlockService(session_factory()).block("500")

    query = MagicMock()
    query.data = "payment_var_1"
    query.from_user.id = 500
    query.from_user.username = None
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query

    # Provide a valid user_state so we get past the early state guards.
    state = MagicMock()
    state.selected_variation_id = "var_1"
    state.quantity = 1

    with (
        patch.object(callbacks, "get_session_factory", return_value=session_factory),
        patch.object(callbacks.state_manager, "get_user_state", return_value=state),
        patch(
            "src.database.services.order_service.OrderService.create_order"
        ) as create_order,
    ):
        asyncio.run(callbacks.handle_payment(update, MagicMock()))

    # The gate must have fired: verify the exact block message was shown.
    # (conftest patches language DB so t() always falls back to "vi".)
    expected = get_translation("errors.user_blocked", "vi")
    query.edit_message_text.assert_awaited_once_with(expected)
    create_order.assert_not_called()


def test_blocked_by_username_cannot_create_order(session_factory):
    from src.bot.handlers import callbacks

    BlockService(session_factory()).block("@ghost")

    query = MagicMock()
    query.data = "payment_var_1"
    query.from_user.id = 999  # id NOT in blocklist
    query.from_user.username = "Ghost"  # username IS blocked
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query

    state = MagicMock()
    state.selected_variation_id = "var_1"
    state.quantity = 1

    with (
        patch.object(callbacks, "get_session_factory", return_value=session_factory),
        patch.object(callbacks.state_manager, "get_user_state", return_value=state),
        patch(
            "src.database.services.order_service.OrderService.create_order"
        ) as create_order,
    ):
        asyncio.run(callbacks.handle_payment(update, MagicMock()))

    # The gate must have fired: verify the exact block message was shown.
    expected = get_translation("errors.user_blocked", "vi")
    query.edit_message_text.assert_awaited_once_with(expected)
    create_order.assert_not_called()
