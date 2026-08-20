from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.bot.handlers import apitoken, balance, callbacks, commands
from src.dashboard import main as dashboard_main
from src.dashboard.routers import product_upload
from src.database.models import DeliveryType, Product, ProductVariation
from src.database.models.base import Base
from src.database.services.app_settings_service import AppSettingsService
from src.ipn import processor as processor_module


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.mark.asyncio
async def test_start_uses_runtime_identity_and_support_lines(monkeypatch):
    settings = SimpleNamespace(
        system_name="Example Shop",
        support_line_1="@example_support",
        support_line_2="support@example.com",
    )
    session = MagicMock()
    monkeypatch.setenv("SYSTEM_NAME", "Stale Environment Name")
    monkeypatch.setattr(commands, "get_session_factory", lambda: lambda: session)
    monkeypatch.setattr(
        commands,
        "AppSettingsService",
        lambda _session: SimpleNamespace(get_settings=lambda: settings),
    )
    monkeypatch.setattr(commands, "BotUserService", MagicMock())

    def translate(key, _update, **kwargs):
        values = {
            "commands.start.welcome": "Welcome",
            "commands.start.description": f"Shop: {kwargs.get('system_name')}",
            "commands.start.help_hint": "Help",
            "start_menu.title": "Menu",
        }
        return values.get(key, key)

    monkeypatch.setattr(commands, "t", translate)
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(
        effective_user=SimpleNamespace(
            id=123,
            username="user",
            first_name="Test",
            last_name=None,
        ),
        message=message,
    )

    await commands.start(update, SimpleNamespace())

    welcome = message.reply_text.await_args_list[0].args[0]
    assert "Shop: Example Shop" in welcome
    assert welcome.endswith("Help\n@example_support\nsupport@example.com")
    assert "Stale Environment Name" not in welcome
    session.close.assert_called_once()


@pytest.mark.asyncio
async def test_start_keeps_settings_after_track_user_commit(monkeypatch, db_session):
    AppSettingsService(db_session).update_settings(
        system_name="Committed Shop",
        support_line_1="@committed_support",
        support_line_2="support@committed.example",
    )
    monkeypatch.setattr(commands, "get_session_factory", lambda: lambda: db_session)
    monkeypatch.setattr(commands, "get_persistent_keyboard", lambda _update: MagicMock())

    def translate(key, _update, **kwargs):
        values = {
            "commands.start.welcome": "Welcome",
            "commands.start.description": f"Shop: {kwargs.get('system_name')}",
            "commands.start.help_hint": "Help",
            "start_menu.title": "Menu",
        }
        return values.get(key, key)

    monkeypatch.setattr(commands, "t", translate)
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(
        effective_user=SimpleNamespace(
            id=456,
            username="committed_user",
            first_name="Committed",
            last_name=None,
        ),
        message=message,
    )

    await commands.start(update, SimpleNamespace())

    welcome = message.reply_text.await_args_list[0].args[0]
    assert "Shop: Committed Shop" in welcome
    assert welcome.endswith(
        "Help\n@committed_support\nsupport@committed.example"
    )


@pytest.mark.asyncio
async def test_setadmin_mutations_require_configured_owner(monkeypatch):
    owner_check = MagicMock(return_value=True)
    add_admin = MagicMock(return_value=True)
    monkeypatch.setattr(commands, "is_admin", lambda _user_id: True)
    monkeypatch.setattr(commands, "is_owner", owner_check, raising=False)
    monkeypatch.setattr(commands, "add_admin", add_admin)
    monkeypatch.setattr(
        commands, "_resolve_admin_target", AsyncMock(return_value=222)
    )
    monkeypatch.setattr(commands, "t", lambda key, _update, **_kwargs: key)
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=123),
        message=SimpleNamespace(reply_text=AsyncMock()),
    )

    await commands.setadmin_command(update, SimpleNamespace(args=["222"]))

    owner_check.assert_called_once_with(123)
    add_admin.assert_called_once_with(222, added_by=123)


@pytest.mark.asyncio
async def test_setadmin_list_labels_configured_owner(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(commands, "get_session_factory", lambda: lambda: session)
    monkeypatch.setattr(commands, "is_admin", lambda _user_id: True)
    monkeypatch.setattr(commands, "is_owner", lambda user_id: user_id == 123, raising=False)
    monkeypatch.setattr(commands, "get_admin_telegram_ids", lambda: [123, 222])
    monkeypatch.setattr(
        commands,
        "BotUserService",
        lambda _session: SimpleNamespace(get_user_by_telegram_id=lambda _user_id: None),
    )
    monkeypatch.setattr(
        "src.database.services.bot_admin_service.BotAdminService",
        lambda _session: SimpleNamespace(list_all=list),
    )
    monkeypatch.setattr(
        commands,
        "t",
        lambda key, _update, **kwargs: (
            " [owner]"
            if key == "commands.setadmin.owner_label"
            else kwargs.get("ids", key)
        ),
    )
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=123),
        message=message,
    )

    await commands.setadmin_command(update, SimpleNamespace(args=["list"]))

    response = message.reply_text.await_args.args[0]
    assert "123 [owner]" in response
    assert "222 [owner]" not in response
    session.close.assert_called_once()


def test_api_menu_keyboard_uses_runtime_docs_url(monkeypatch):
    monkeypatch.setattr(apitoken, "t", lambda key, _update: key)
    update = SimpleNamespace()
    keyboard = apitoken._api_menu_keyboard(
        update,
        has_token=False,
        api_docs_url="https://shop.example/api",
    )
    assert any(
        button.url == "https://shop.example/api"
        for row in keyboard.inline_keyboard
        for button in row
    )


@pytest.mark.parametrize(
    ("handler_name", "has_token"),
    [
        ("api_command", True),
        ("handle_api_menu", True),
        ("handle_api_create", True),
        ("handle_api_revoke", False),
    ],
)
@pytest.mark.asyncio
async def test_api_handlers_pass_runtime_docs_url(
    monkeypatch, handler_name, has_token
):
    session = MagicMock()
    settings = SimpleNamespace(api_docs_url="https://shop.example/api")
    keyboard_spy = MagicMock(return_value=MagicMock())

    class FakeBotUserService:
        def __init__(self, _session):
            pass

        def get_user_by_telegram_id(self, _user_id):
            return SimpleNamespace(api_token="token")

        def generate_api_token(self, _user_id):
            return "token"

        def revoke_api_token(self, _user_id):
            return True

    monkeypatch.setattr(apitoken, "get_session_factory", lambda: lambda: session)
    monkeypatch.setattr(apitoken, "BotUserService", FakeBotUserService)
    monkeypatch.setattr(
        apitoken,
        "AppSettingsService",
        lambda _session: SimpleNamespace(get_settings=lambda: settings),
        raising=False,
    )
    monkeypatch.setattr(apitoken, "_api_menu_keyboard", keyboard_spy)
    monkeypatch.setattr(apitoken, "t", lambda key, _update, **_kwargs: key)
    user = SimpleNamespace(id=123)
    update = SimpleNamespace(
        effective_user=user,
        message=SimpleNamespace(reply_text=AsyncMock()),
        callback_query=SimpleNamespace(
            from_user=user,
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
        ),
    )

    await getattr(apitoken, handler_name)(update, SimpleNamespace())

    keyboard_spy.assert_called_once_with(
        update,
        has_token=has_token,
        api_docs_url="https://shop.example/api",
    )
    session.close.assert_called_once()


def test_upload_notification_header_uses_runtime_system_name(db_session):
    AppSettingsService(db_session).update_settings(system_name="Example Shop")
    db_session.add(
        Product(
            id="product-1",
            name="Product",
            description="",
            delivery_type=DeliveryType.PRE_UPLOADED,
            is_active=True,
        )
    )
    db_session.add(
        ProductVariation(
            id="variation-1",
            product_id="product-1",
            name="Variation",
            price=10_000,
            stock=0,
            is_active=True,
        )
    )
    db_session.commit()

    entries = product_upload._collect_upload_notification_messages(
        db_session,
        [{"product_id": "product-1", "variation_id": "variation-1"}],
        {"errors": []},
    )

    assert entries[0]["message"].startswith("📢 Example Shop ")


def test_delivery_file_header_uses_runtime_system_name(monkeypatch, tmp_path):
    settings_session = MagicMock()
    captured_messages = []

    class FakeBot:
        def send_message(self, **kwargs):
            captured_messages.append(kwargs["text"])
            return SimpleNamespace(message_id=1)

        def send_document(self, **_kwargs):
            return SimpleNamespace(message_id=2)

    monkeypatch.setenv("SYSTEM_NAME", "Stale Environment Name")
    monkeypatch.setattr(processor_module, "DELIVERY_FILES_DIR", tmp_path)
    monkeypatch.setattr(processor_module, "run_async", lambda result: result)
    monkeypatch.setattr(
        processor_module, "get_session_factory", lambda: lambda: settings_session
    )
    monkeypatch.setattr(
        processor_module,
        "AppSettingsService",
        lambda _session: SimpleNamespace(
            get_settings=lambda: SimpleNamespace(system_name="Example Shop")
        ),
        raising=False,
    )
    processor = processor_module.IPNOrderProcessor(bot=FakeBot())

    processor._send_pre_uploaded_products(
        123,
        "SHOP12345678",
        [{"data": {"delivery_data": "secret"}}],
    )

    assert "Example Shop" in captured_messages[0]
    assert "Stale Environment Name" not in captured_messages[0]
    settings_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_dashboard_root_uses_runtime_system_name(monkeypatch):
    settings = SimpleNamespace(system_name="Example Shop")
    monkeypatch.setattr(
        dashboard_main,
        "AppSettingsService",
        lambda _session: SimpleNamespace(get_settings=lambda: settings),
        raising=False,
    )

    response = await dashboard_main.root(db=MagicMock())

    assert response == {
        "message": "Example Shop Dashboard API",
        "version": "1.0.0",
    }


def test_dashboard_openapi_metadata_is_generic():
    assert dashboard_main.app.title == "Bot Order Dashboard API"
    assert dashboard_main.app.description == "Dashboard API for Bot Order System"


@pytest.mark.asyncio
async def test_topup_payment_link_uses_runtime_settings(monkeypatch):
    session = MagicMock()
    topup = SimpleNamespace(
        id="TUabcdefghi",
        payos_order_code=None,
        payos_checkout_url=None,
        payos_qr_code=None,
        payment_provider=None,
        payment_message_ids=None,
    )
    payos = SimpleNamespace(create_payment_link=MagicMock(return_value={"data": {}}))
    settings = SimpleNamespace(
        order_prefix="SHOP", bot_url="https://t.me/example_shop_bot"
    )
    monkeypatch.setattr(balance, "get_session_factory", lambda: lambda: session)
    monkeypatch.setattr(
        balance,
        "TopupService",
        lambda _session: SimpleNamespace(get_by_id=lambda _topup_id: topup),
    )
    monkeypatch.setattr(
        balance,
        "OrderService",
        lambda _session: SimpleNamespace(generate_payos_order_code=lambda: 123456789),
    )
    monkeypatch.setattr(
        balance,
        "AppSettingsService",
        lambda _session: SimpleNamespace(get_settings=lambda: settings),
    )
    monkeypatch.setattr(balance, "build_payos_client", lambda: payos)
    monkeypatch.setattr(balance, "EmojiPlaceholderService", lambda _session: None)
    monkeypatch.setattr(balance, "render_emoji", lambda text, _service: (text, None))
    monkeypatch.setattr(balance, "t", lambda key, _update, **_kwargs: key)
    monkeypatch.setattr(balance, "state_manager", MagicMock())
    context = SimpleNamespace(
        bot=SimpleNamespace(
            send_message=AsyncMock(return_value=SimpleNamespace(message_id=1)),
            send_photo=AsyncMock(return_value=SimpleNamespace(message_id=2)),
        )
    )

    await balance._create_topup_qr(
        SimpleNamespace(), context, topup.id, 10_000, 123, None
    )

    kwargs = payos.create_payment_link.call_args.kwargs
    assert kwargs["description"] == f"SHOP{topup.id}"[:9]
    assert kwargs["return_url"] == settings.bot_url
    assert kwargs["cancel_url"] == settings.bot_url


@pytest.mark.asyncio
async def test_order_payment_link_uses_runtime_settings(monkeypatch):
    session = MagicMock()
    order = SimpleNamespace(
        id="SHOP12345678",
        user_id=123,
        total_amount=10_000,
        payos_order_code=None,
        payos_checkout_url=None,
        payos_qr_code=None,
        payment_provider=None,
        payment_message_ids=None,
    )
    order_service = SimpleNamespace(
        get_order_by_id=lambda _order_id: order,
        generate_payos_order_code=lambda: 123456789,
    )
    payos = SimpleNamespace(create_payment_link=MagicMock(return_value={"data": {}}))
    settings = SimpleNamespace(bot_url="https://t.me/example_shop_bot")
    monkeypatch.setattr(callbacks, "get_session_factory", lambda: lambda: session)
    monkeypatch.setattr(callbacks, "OrderService", lambda _session: order_service)
    monkeypatch.setattr(
        callbacks,
        "AppSettingsService",
        lambda _session: SimpleNamespace(get_settings=lambda: settings),
    )
    monkeypatch.setattr(callbacks, "build_payos_client", lambda: payos)
    monkeypatch.setattr(
        callbacks, "format_payment_message", lambda *_args: ("payment", "caption")
    )
    monkeypatch.setattr(callbacks, "EmojiPlaceholderService", lambda _session: None)
    monkeypatch.setattr(callbacks, "render_emoji", lambda text, _service: (text, None))
    monkeypatch.setattr(callbacks, "state_manager", MagicMock())
    context = SimpleNamespace(
        bot=SimpleNamespace(
            send_message=AsyncMock(
                side_effect=[
                    SimpleNamespace(message_id=1),
                    SimpleNamespace(message_id=2),
                ]
            ),
            send_photo=AsyncMock(return_value=SimpleNamespace(message_id=3)),
        )
    )
    update = SimpleNamespace(effective_user=SimpleNamespace(id=123))

    await callbacks._create_qr_for_order(order.id, update, context)

    kwargs = payos.create_payment_link.call_args.kwargs
    assert kwargs["description"] == order.id[:9]
    assert kwargs["return_url"] == settings.bot_url
    assert kwargs["cancel_url"] == settings.bot_url
