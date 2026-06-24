"""Tests for the /export Telegram handlers (logic via mocks)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.bot.handlers.export as export
from src.bot.handlers.commands import state_manager
from src.bot.states.state_manager import UserState


@pytest.fixture(autouse=True)
def clear_state():
    state_manager._states.clear()
    yield
    state_manager._states.clear()


def _callback_update(user_id=100, data="export_go"):
    update = MagicMock()
    update.callback_query = MagicMock()
    update.callback_query.from_user.id = user_id
    update.callback_query.data = data
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.effective_user.id = user_id
    return update


@pytest.mark.asyncio
async def test_start_with_no_products_shows_empty_message():
    update = _callback_update(data="start_export")
    with patch.object(export, "get_session_factory") as gsf, \
         patch.object(export.ExportService, "get_exportable_products", return_value=[]):
        gsf.return_value.return_value = MagicMock()  # session
        await export.handle_export_start(update, MagicMock())
    update.callback_query.edit_message_text.assert_awaited()
    text = update.callback_query.edit_message_text.call_args.args[0]
    assert "no delivered" in text.lower() or "chưa có" in text.lower()


@pytest.mark.asyncio
async def test_start_with_products_stores_state_and_lists():
    update = _callback_update(data="start_export")
    products = [{"id": "p1", "name": "Netflix"}, {"id": "p2", "name": "Spotify"}]
    with patch.object(export, "get_session_factory") as gsf, \
         patch.object(export.ExportService, "get_exportable_products", return_value=products):
        gsf.return_value.return_value = MagicMock()
        await export.handle_export_start(update, MagicMock())
    st = state_manager.get_user_state(100)
    assert st.export_products == products
    kb = update.callback_query.edit_message_text.call_args.kwargs["reply_markup"]
    # one button per product + a cancel row
    assert len(kb.inline_keyboard) == 3


@pytest.mark.asyncio
async def test_variant_toggle_flips_selection():
    st = UserState()
    st.export_product_id = "p1"
    st.export_products = [{"id": "p1", "name": "Netflix"}]
    st.export_variations = [{"id": "v1", "name": "1 Month"}, {"id": "v2", "name": "12 Month"}]
    state_manager.set_user_state(100, st)

    with patch.object(export, "get_session_factory") as gsf:
        gsf.return_value.return_value = MagicMock()  # session for emoji rendering
        update = _callback_update(data="export_var_0")
        await export.handle_export_variant_toggle(update, MagicMock())
        assert state_manager.get_user_state(100).export_selected_variation_ids == {"v1"}

        update2 = _callback_update(data="export_var_0")
        await export.handle_export_variant_toggle(update2, MagicMock())
        assert state_manager.get_user_state(100).export_selected_variation_ids == set()


@pytest.mark.asyncio
async def test_generate_with_nothing_selected_alerts():
    st = UserState()
    st.export_product_id = "p1"
    st.export_selected_variation_ids = set()
    state_manager.set_user_state(100, st)

    update = _callback_update(data="export_go")
    await export.handle_export_generate(update, MagicMock())
    update.callback_query.answer.assert_awaited()
    assert update.callback_query.answer.call_args.kwargs.get("show_alert") is True


@pytest.mark.asyncio
async def test_cancel_clears_state():
    state_manager.set_user_state(100, UserState())
    update = _callback_update(data="export_cancel")
    await export.handle_export_cancel(update, MagicMock())
    assert state_manager.get_user_state(100) is None


@pytest.mark.asyncio
async def test_generate_zero_sent_shows_none_exported_message():
    """When every get_variant_export returns None, sent==0 should show none_exported, not done."""
    st = UserState()
    st.export_product_id = "p1"
    st.export_selected_variation_ids = {"v1"}
    state_manager.set_user_state(100, st)

    update = _callback_update(data="export_go")
    ctx = MagicMock()
    ctx.bot.send_document = AsyncMock()

    mock_settings = MagicMock()
    mock_settings.timezone = "Asia/Ho_Chi_Minh"

    with patch.object(export, "get_session_factory") as gsf, \
         patch.object(export.ExportService, "get_variant_export", return_value=None), \
         patch.object(export.AppSettingsService, "get_settings", return_value=mock_settings):
        gsf.return_value.return_value = MagicMock()
        await export.handle_export_generate(update, ctx)

    # State should be cleared
    assert state_manager.get_user_state(100) is None

    # Should show none_exported (Vietnamese), not done
    text = update.callback_query.edit_message_text.call_args.args[0]
    assert "Không thể xuất" in text
    assert "Đã xuất" not in text
