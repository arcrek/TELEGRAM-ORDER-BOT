"""
Tests for the dashboard "Việc cần làm" (todo) statistics items.

Regression coverage for a PostgreSQL-only bug: the pending-upgrade-orders
query used ``.distinct(Order.id)`` together with ``ORDER BY created_at``,
which PostgreSQL rejects ("SELECT DISTINCT ON expressions must match initial
ORDER BY expressions"). SQLite silently renders a plain DISTINCT, so the error
never surfaced in tests — only in production, where the failing endpoint made
the whole todo panel render empty.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from src.database.connection import (
    create_engine_instance,
    get_session_factory,
    init_database,
)
from src.database.models import Order, OrderItem, Product
from src.database.models.enums import DeliveryType, OrderStatus
from src.database.services.statistics_service import StatisticsService


@pytest.fixture
def db_session():
    engine = create_engine_instance("sqlite:///:memory:")
    init_database(engine)
    session_factory = get_session_factory(engine)
    session = session_factory()
    yield session
    session.close()


def _seed_pending_upgrade_order(session: Session) -> str:
    product = Product(
        id="prod_upgrade",
        name="Upgrade Product",
        description="An upgrade product",
        delivery_type=DeliveryType.UPGRADE,
        is_active=True,
    )
    session.add(product)
    order = Order(
        id="UP123",
        user_id=42,
        status=OrderStatus.PENDING,
        total_amount=50000,
        discount_amount=0,
        created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    session.add(order)
    session.add(
        OrderItem(
            id="oi_1",
            order_id=order.id,
            product_id=product.id,
            quantity=1,
            unit_price=50000,
            subtotal=50000,
        )
    )
    session.commit()
    return order.id


def test_pending_upgrade_order_appears_in_todo(db_session: Session):
    """A pending order for an UPGRADE product must surface in the todo panel."""
    order_id = _seed_pending_upgrade_order(db_session)

    result = StatisticsService(db_session).get_todo_items()

    ids = [o["id"] for o in result["upgrade_orders"]]
    assert order_id in ids
    assert result["upgrade_orders_count"] >= 1


def test_upgrade_orders_query_is_valid_postgresql(db_session: Session):
    """The upgrade-orders query must compile to valid PostgreSQL.

    A ``DISTINCT ON (orders.id)`` combined with ``ORDER BY orders.created_at``
    is rejected by PostgreSQL. Guard against re-introducing any DISTINCT here:
    the query is written without one (the join multiplication is removed via a
    subquery), so the compiled SQL must contain no DISTINCT at all.
    """
    query = StatisticsService(db_session)._upgrade_orders_query()
    compiled = str(query.statement.compile(dialect=postgresql.dialect()))
    assert "DISTINCT" not in compiled.upper(), compiled
