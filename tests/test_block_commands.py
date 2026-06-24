"""Tests for /block and /unblock command handlers."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models.base import Base
from src.database.services.block_service import BlockService


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _make_update(text_args):
    update = MagicMock()
    update.effective_user.id = 42
    update.message.reply_text = AsyncMock()
    return update


def _make_context(args):
    context = MagicMock()
    context.args = args
    return context


def test_block_command_rejects_non_admin(session_factory):
    from src.bot.handlers import commands

    update = _make_update([])
    context = _make_context(["123"])
    with patch.object(commands, "is_admin", return_value=False):
        asyncio.run(commands.block_command(update, context))
    update.message.reply_text.assert_awaited_once()
    # No block created: factory never used because we patched is_admin off.


def test_block_command_blocks_id_for_admin(session_factory):
    from src.bot.handlers import commands

    update = _make_update([])
    context = _make_context(["123"])
    with (
        patch.object(commands, "is_admin", return_value=True),
        patch.object(commands, "get_session_factory", return_value=session_factory),
    ):
        asyncio.run(commands.block_command(update, context))
    update.message.reply_text.assert_awaited_once()
    # Verify the block landed.
    svc = BlockService(session_factory())
    assert svc.is_blocked(123, None) is True


def test_block_command_usage_when_no_args(session_factory):
    from src.bot.handlers import commands

    update = _make_update([])
    context = _make_context([])
    with (
        patch.object(commands, "is_admin", return_value=True),
        patch.object(commands, "get_session_factory", return_value=session_factory),
    ):
        asyncio.run(commands.block_command(update, context))
    update.message.reply_text.assert_awaited_once()


def test_unblock_command_removes_block(session_factory):
    from src.bot.handlers import commands

    # Seed a block first.
    BlockService(session_factory()).block("123")
    update = _make_update([])
    context = _make_context(["123"])
    with (
        patch.object(commands, "is_admin", return_value=True),
        patch.object(commands, "get_session_factory", return_value=session_factory),
    ):
        asyncio.run(commands.unblock_command(update, context))
    update.message.reply_text.assert_awaited_once()
    assert BlockService(session_factory()).is_blocked(123, None) is False
