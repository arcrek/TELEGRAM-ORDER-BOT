"""
Tests for OrderNotificationService.
"""
import pytest
from unittest.mock import Mock, ANY
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.base import Base
from src.database.models.enums import OrderStatus
from src.database.models import DeliveryType
from src.database.services.order_service import OrderService
from src.database.services.product_service import ProductService
from src.database.services.variation_service import VariationService
from src.database.services.notification_settings_service import NotificationSettingsService
from src.database.services.order_notification_service import OrderNotificationService


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_order(db_session):
    """Create a minimal order with item for formatting."""
    product_service = ProductService(db_session)
    variation_service = VariationService(db_session)
    order_service = OrderService(db_session)

    product_service.create_product(
        {
            "id": "prod_1",
            "name": "Test Product",
            "description": "Test",
            "delivery_type": DeliveryType.SUPPLIER_BASED,
            "is_active": True,
        }
    )
    variation_service.create_variation(
        {
            "id": "var_1",
            "product_id": "prod_1",
            "name": "Var",
            "price": 1000,
            "stock": 10,
            "is_active": True,
        }
    )

    order = order_service.create_order(user_id=111, variation_id="var_1", quantity=1)
    assert order.status == OrderStatus.PENDING
    return order


@pytest.fixture
def mock_bot():
    bot = Mock()
    bot.send_message = Mock()
    return bot


@pytest.mark.asyncio
async def test_order_notification_skips_when_disabled(db_session, sample_order, mock_bot):
    settings_service = NotificationSettingsService(db_session)
    settings_service.update_settings(
        order_notify_enabled=False,
        order_notify_on_created=True,
        order_notify_on_paid=True,
        whitelist_chat_ids=[999],
    )

    service = OrderNotificationService(db_session, bot=mock_bot)
    result = await service.send_order_created_async(sample_order.id)

    assert result.get("skipped") == "disabled_or_empty_whitelist"
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_order_notification_sends_to_whitelist_when_enabled(db_session, sample_order, mock_bot):
    settings_service = NotificationSettingsService(db_session)
    settings_service.update_settings(
        order_notify_enabled=True,
        order_notify_on_created=True,
        order_notify_on_paid=False,
        whitelist_chat_ids=[999, "-1001:77"],
    )

    service = OrderNotificationService(db_session, bot=mock_bot)
    result = await service.send_order_created_async(sample_order.id)

    # Two recipients
    assert result["total"] == 2
    assert mock_bot.send_message.call_count == 2
    mock_bot.send_message.assert_any_call(chat_id=999, text=ANY)
    mock_bot.send_message.assert_any_call(chat_id=-1001, text=ANY, message_thread_id=77)


@pytest.mark.asyncio
async def test_order_notification_respects_event_toggle(db_session, sample_order, mock_bot):
    settings_service = NotificationSettingsService(db_session)
    settings_service.update_settings(
        order_notify_enabled=True,
        order_notify_on_created=False,
        order_notify_on_paid=True,
        whitelist_chat_ids=[999],
    )

    service = OrderNotificationService(db_session, bot=mock_bot)
    result = await service.send_order_created_async(sample_order.id)
    assert result.get("skipped") == "event_disabled"
    mock_bot.send_message.assert_not_called()

