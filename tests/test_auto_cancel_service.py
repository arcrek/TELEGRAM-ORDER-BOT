"""
Tests for auto-cancel service.
Following TDD: Write tests first, then implement service.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Order, OrderItem, Product, ProductVariation
from src.database.models.base import Base
from src.database.models.enums import DeliveryType, OrderStatus
from src.database.services.auto_cancel_service import AutoCancelService


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
def sample_product(db_session):
    """Create a sample product for testing."""
    product = Product(
        id="prod_1",
        name="Test Product",
        description="Test description",
        delivery_type=DeliveryType.PRE_UPLOADED,
        is_active=True,
    )
    db_session.add(product)
    db_session.commit()
    return product


@pytest.fixture
def sample_variation(db_session, sample_product):
    """Create a sample variation for testing."""
    variation = ProductVariation(
        id="var_1",
        product_id="prod_1",
        name="Pro 12M 1PCS",
        price=40000,
        stock=100,
        is_active=True,
    )
    db_session.add(variation)
    db_session.commit()
    return variation


@pytest.fixture
def auto_cancel_service(db_session):
    """Create auto-cancel service instance."""
    return AutoCancelService(db_session, bot_instance=None)


class TestAutoCancelService:
    """Test AutoCancelService class."""

    def test_find_expired_pending_orders(self, auto_cancel_service, db_session, sample_variation):
        """Test finding expired PENDING orders."""
        # Create an expired PENDING order (created 35 minutes ago)
        expired_time = datetime.now(timezone.utc) - timedelta(minutes=35)
        expired_order = Order(
            id="order_expired",
            user_id=123456789,
            status=OrderStatus.PENDING,
            total_amount=40000,
            created_at=expired_time,
        )
        db_session.add(expired_order)
        
        # Create order item
        order_item = OrderItem(
            id="item_1",
            order_id="order_expired",
            product_id="prod_1",
            variation_id="var_1",
            quantity=1,
            unit_price=40000,
            subtotal=40000,
        )
        db_session.add(order_item)
        
        # Create a recent PENDING order (created 10 minutes ago)
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        recent_order = Order(
            id="order_recent",
            user_id=123456789,
            status=OrderStatus.PENDING,
            total_amount=40000,
            created_at=recent_time,
        )
        db_session.add(recent_order)
        
        # Create a PAID order (should not be found)
        paid_order = Order(
            id="order_paid",
            user_id=123456789,
            status=OrderStatus.PAID,
            total_amount=40000,
            created_at=expired_time,
        )
        db_session.add(paid_order)
        
        db_session.commit()
        
        # Find expired orders
        expired_orders = auto_cancel_service.find_expired_pending_orders(minutes=30)
        
        assert len(expired_orders) == 1
        assert expired_orders[0].id == "order_expired"

    def test_auto_cancel_order_success(self, auto_cancel_service, db_session, sample_variation):
        """Test successfully auto-cancelling an expired order."""
        expired_time = datetime.now(timezone.utc) - timedelta(minutes=35)
        order = Order(
            id="order_expired",
            user_id=123456789,
            status=OrderStatus.PENDING,
            total_amount=40000,
            created_at=expired_time,
        )
        db_session.add(order)
        db_session.commit()
        
        result = auto_cancel_service.auto_cancel_order(order, send_notification=False)
        
        assert result is True
        
        # Verify order is cancelled
        db_session.refresh(order)
        assert order.status == OrderStatus.CANCELLED

    def test_auto_cancel_order_already_paid(self, auto_cancel_service, db_session, sample_variation):
        """Test auto-cancelling an order that was already paid (race condition)."""
        expired_time = datetime.now(timezone.utc) - timedelta(minutes=35)
        order = Order(
            id="order_paid",
            user_id=123456789,
            status=OrderStatus.PAID,  # Already paid
            total_amount=40000,
            created_at=expired_time,
        )
        db_session.add(order)
        db_session.commit()
        
        result = auto_cancel_service.auto_cancel_order(order, send_notification=False)
        
        assert result is False
        
        # Verify order is still PAID
        db_session.refresh(order)
        assert order.status == OrderStatus.PAID

    def test_auto_cancel_order_already_cancelled(self, auto_cancel_service, db_session, sample_variation):
        """Test auto-cancelling an order that was already cancelled."""
        expired_time = datetime.now(timezone.utc) - timedelta(minutes=35)
        order = Order(
            id="order_cancelled",
            user_id=123456789,
            status=OrderStatus.CANCELLED,  # Already cancelled
            total_amount=40000,
            created_at=expired_time,
        )
        db_session.add(order)
        db_session.commit()
        
        result = auto_cancel_service.auto_cancel_order(order, send_notification=False)
        
        assert result is False
        
        # Verify order is still CANCELLED
        db_session.refresh(order)
        assert order.status == OrderStatus.CANCELLED

    def test_process_expired_orders(self, auto_cancel_service, db_session, sample_variation):
        """Test processing multiple expired orders."""
        expired_time = datetime.now(timezone.utc) - timedelta(minutes=35)
        
        # Create multiple expired orders
        for i in range(3):
            order = Order(
                id=f"order_expired_{i}",
                user_id=123456789 + i,
                status=OrderStatus.PENDING,
                total_amount=40000,
                created_at=expired_time,
            )
            db_session.add(order)
        
        # Create a recent order (should not be processed)
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        recent_order = Order(
            id="order_recent",
            user_id=123456789,
            status=OrderStatus.PENDING,
            total_amount=40000,
            created_at=recent_time,
        )
        db_session.add(recent_order)
        
        db_session.commit()
        
        # Process expired orders
        results = auto_cancel_service.process_expired_orders(minutes=30, send_notification=False)
        
        assert results["found"] == 3
        assert results["cancelled"] == 3
        assert results["skipped"] == 0
        assert results["failed"] == 0
        
        # Verify all expired orders are cancelled
        for i in range(3):
            order = db_session.query(Order).filter_by(id=f"order_expired_{i}").first()
            assert order.status == OrderStatus.CANCELLED
        
        # Verify recent order is still PENDING
        recent_order = db_session.query(Order).filter_by(id="order_recent").first()
        assert recent_order.status == OrderStatus.PENDING

    def test_process_expired_orders_mixed_status(self, auto_cancel_service, db_session, sample_variation):
        """Test processing expired orders with mixed statuses (race conditions)."""
        expired_time = datetime.now(timezone.utc) - timedelta(minutes=35)
        
        # Create expired PENDING order
        pending_order = Order(
            id="order_pending",
            user_id=123456789,
            status=OrderStatus.PENDING,
            total_amount=40000,
            created_at=expired_time,
        )
        db_session.add(pending_order)
        
        # Create expired PAID order (simulating race condition)
        paid_order = Order(
            id="order_paid",
            user_id=123456789,
            status=OrderStatus.PAID,
            total_amount=40000,
            created_at=expired_time,
        )
        db_session.add(paid_order)
        
        db_session.commit()
        
        # Process expired orders
        results = auto_cancel_service.process_expired_orders(minutes=30, send_notification=False)
        
        assert results["found"] == 1  # Only PENDING orders are found
        assert results["cancelled"] == 1
        assert results["skipped"] == 0
        
        # Verify PENDING order is cancelled
        pending_order = db_session.query(Order).filter_by(id="order_pending").first()
        assert pending_order.status == OrderStatus.CANCELLED
        
        # Verify PAID order is still PAID
        paid_order = db_session.query(Order).filter_by(id="order_paid").first()
        assert paid_order.status == OrderStatus.PAID


def test_run_coro_falls_back_without_main_loop():
    """With no main loop set, the helper still runs the coroutine (test/back-compat path)."""
    from src.database.services.auto_cancel_service import AutoCancelService

    svc = AutoCancelService(session=None, bot_instance=None)
    ran = {"value": False}

    async def _coro():
        ran["value"] = True

    svc._run_coro(_coro())
    assert ran["value"] is True


def test_run_coro_uses_main_loop_when_running():
    """When a running main loop is provided, the helper schedules onto it."""
    import asyncio
    import threading

    from src.database.services.auto_cancel_service import AutoCancelService

    loop = asyncio.new_event_loop()
    t = threading.Thread(target=loop.run_forever, daemon=True)
    t.start()
    try:
        svc = AutoCancelService(session=None, bot_instance=None, main_loop=loop)
        seen = {"loop": None}

        async def _coro():
            seen["loop"] = asyncio.get_running_loop()

        svc._run_coro(_coro())
        assert seen["loop"] is loop
    finally:
        loop.call_soon_threadsafe(loop.stop)
        t.join(timeout=2)
        loop.close()

