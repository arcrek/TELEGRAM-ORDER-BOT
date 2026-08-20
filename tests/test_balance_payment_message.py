import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.bot.handlers import callbacks
from src.database.models.enums import OrderStatus


@pytest.mark.asyncio
async def test_balance_payment_message_updates_when_delivered(monkeypatch):
    class Loop:
        async def run_in_executor(self, _executor, call):
            return call()

    class Session:
        def close(self):
            pass

    class OrderService:
        def __init__(self, _session):
            pass

        def get_order_by_id(self, _order_id):
            return SimpleNamespace(total_amount=10_000, status=OrderStatus.DELIVERED)

    class Processor:
        def process_balance_paid_order(self, **_kwargs):
            return True

    monkeypatch.setattr(callbacks, "get_session_factory", lambda: Session)
    monkeypatch.setattr(asyncio, "get_running_loop", lambda: Loop())
    monkeypatch.setattr(callbacks, "OrderService", OrderService)
    monkeypatch.setattr(callbacks.state_manager, "get_user_state", lambda _user_id: None)
    monkeypatch.setattr(
        "src.database.services.bot_user_service.BotUserService.get_user_by_telegram_id",
        lambda _self, _user_id: SimpleNamespace(id="user_1"),
    )
    monkeypatch.setattr(
        "src.database.services.balance_service.BalanceService.pay_order_with_balance",
        lambda _self, _order_id, _bot_user: (True, "ok"),
    )
    monkeypatch.setattr("src.ipn.get_ipn_processor", lambda: Processor())
    monkeypatch.setattr("src.bot.utils.language.t", lambda key, _update: key)

    query = SimpleNamespace(edit_message_text=AsyncMock())
    await callbacks._pay_with_balance_locked(
        SimpleNamespace(), SimpleNamespace(), query, 123, "order_1"
    )

    assert [call.args[0] for call in query.edit_message_text.await_args_list] == [
        "balance.balance_paid_success",
        "balance.balance_paid_delivered",
    ]
