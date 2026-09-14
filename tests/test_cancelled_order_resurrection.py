"""
Regression tests for zombie order resurrection prevention ([CRIT-04]).

Verifies that cancelled or refunded orders receiving late PayOS IPNs:
1. Are immediately rejected with return code False.
2. Are NOT transitioned to PAID, PROCESSING, or DELIVERED.
3. Do NOT trigger stock delivery or allocate inventory.
4. Record the incoming payment_transaction_id for manual reconciliation.
5. Trigger an admin alert via OrderNotificationService.send_late_payment_alert.
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src.database.models import (
    Base,
    BotUser,
    Order,
    OrderItem,
    OrderStatus,
    PreUploadedProduct,
    Product,
    ProductVariation,
)
from src.database.models.enums import DeliveryType
from src.ipn.processor import IPNOrderProcessor


@pytest.fixture
def session_factory(tmp_path):
    db_url = f"sqlite:///{tmp_path}/resurrection_test.db"
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture
def setup_cancelled_order_with_stock(session_factory):
    session = session_factory()
    try:
        user = BotUser(telegram_user_id=200001, username="test_buyer")
        session.add(user)

        product = Product(
            id="prod_test_01",
            name="Digital Key",
            delivery_type=DeliveryType.PRE_UPLOADED,
        )
        session.add(product)

        variation = ProductVariation(
            id="var_test_01",
            product_id=product.id,
            name="1 Month",
            price=50_000,
        )
        session.add(variation)

        # Create unreserved stock
        stock = PreUploadedProduct(
            id="stock_item_01",
            product_id=product.id,
            variation_id=variation.id,
            product_data='{"license_key": "SECRET_KEY_123"}',
            is_used=False,
        )
        session.add(stock)

        order = Order(
            id="ORD_CANCELLED_01",
            user_id=user.telegram_user_id,
            status=OrderStatus.CANCELLED,
            total_amount=50_000,
        )
        session.add(order)

        order_item = OrderItem(
            id="item_01",
            order_id=order.id,
            product_id=product.id,
            variation_id=variation.id,
            quantity=1,
            unit_price=50_000,
            subtotal=50_000,
        )
        session.add(order_item)

        session.commit()
        return order.id, stock.id
    finally:
        session.close()


def test_cancelled_order_payment_aborts_fulfillment(session_factory, setup_cancelled_order_with_stock):
    order_id, stock_id = setup_cancelled_order_with_stock
    mock_bot = MagicMock()

    with (
        patch("src.ipn.processor.get_session_factory", return_value=session_factory),
        patch("src.ipn.processor.OrderNotificationService") as mock_notif_cls,
    ):
        mock_notif_instance = MagicMock()
        mock_notif_cls.return_value = mock_notif_instance

        processor = IPNOrderProcessor(bot=mock_bot)

        # Late payment arrived for cancelled order
        result = processor.process_payment_success(
            order_id=order_id,
            transaction_id="late_payos_tx_001",
            amount=50_000,
        )

        # Must return False to signal fulfillment was not executed
        assert result is False

        # Must trigger late payment alert to admin
        mock_notif_instance.send_late_payment_alert.assert_called_once()
        args, _ = mock_notif_instance.send_late_payment_alert.call_args
        assert args[1] == "late_payos_tx_001"
        assert args[2] == 50_000

    # Verify database state
    verify_session = session_factory()
    try:
        order = verify_session.execute(select(Order).where(Order.id == order_id)).scalars().one()
        # Status must remain CANCELLED
        assert order.status == OrderStatus.CANCELLED
        # Transaction ID must be recorded for reconciliation
        assert order.payment_transaction_id == "late_payos_tx_001"

        # Stock must NOT be consumed
        stock = verify_session.execute(
            select(PreUploadedProduct).where(PreUploadedProduct.id == stock_id)
        ).scalars().one()
        assert stock.is_used is False
        assert stock.used_by_order_id is None
    finally:
        verify_session.close()


def test_refunded_order_payment_aborts_fulfillment(session_factory):
    session = session_factory()
    try:
        user = BotUser(telegram_user_id=200002, username="test_refund_user")
        session.add(user)

        order = Order(
            id="ORD_REFUNDED_01",
            user_id=user.telegram_user_id,
            status=OrderStatus.REFUNDED,
            total_amount=75_000,
        )
        session.add(order)
        session.commit()
    finally:
        session.close()

    mock_bot = MagicMock()

    with (
        patch("src.ipn.processor.get_session_factory", return_value=session_factory),
        patch("src.ipn.processor.OrderNotificationService") as mock_notif_cls,
    ):
        mock_notif_instance = MagicMock()
        mock_notif_cls.return_value = mock_notif_instance

        processor = IPNOrderProcessor(bot=mock_bot)

        result = processor.process_payment_success(
            order_id="ORD_REFUNDED_01",
            transaction_id="late_refund_tx_002",
            amount=75_000,
        )

        assert result is False
        mock_notif_instance.send_late_payment_alert.assert_called_once()

    verify_session = session_factory()
    try:
        order = verify_session.execute(select(Order).where(Order.id == "ORD_REFUNDED_01")).scalars().one()
        assert order.status == OrderStatus.REFUNDED
        assert order.payment_transaction_id == "late_refund_tx_002"
    finally:
        verify_session.close()
