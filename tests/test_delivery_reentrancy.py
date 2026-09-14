"""
Regression tests for re-entrant digital delivery ([HIGH-01]).

Verifies that calling `PreUploadedService.deliver_order` multiple times on the same order:
1. Allocates and marks the required stock items on the first delivery.
2. Returns the already-delivered items on subsequent calls without consuming secondary stock.
3. Preserves remaining available inventory across duplicate/concurrent delivery attempts.
"""

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
from src.database.services.pre_uploaded_service import PreUploadedService


@pytest.fixture
def session_factory(tmp_path):
    db_url = f"sqlite:///{tmp_path}/reentrancy_test.db"
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


def test_deliver_order_is_idempotent_and_does_not_deplete_extra_stock(session_factory):
    session = session_factory()
    try:
        user = BotUser(telegram_user_id=300001, username="test_buyer_reentrant")
        session.add(user)

        product = Product(
            id="prod_reentrant_01",
            name="Streaming Account",
            delivery_type=DeliveryType.PRE_UPLOADED,
        )
        session.add(product)

        variation = ProductVariation(
            id="var_reentrant_01",
            product_id=product.id,
            name="1 Month Shared",
            price=25_000,
        )
        session.add(variation)

        # Upload 3 stock items
        stock_items = [
            PreUploadedProduct(
                id=f"stock_00{i}",
                product_id=product.id,
                variation_id=variation.id,
                product_data=f'{{"account": "user{i}@example.com:pass{i}"}}',
                is_used=False,
            )
            for i in range(1, 4)
        ]
        session.add_all(stock_items)

        # Create order for quantity 1
        order = Order(
            id="ORD_REENTRANT_01",
            user_id=user.telegram_user_id,
            status=OrderStatus.PAID,
            total_amount=25_000,
        )
        session.add(order)

        order_item = OrderItem(
            id="item_reentrant_01",
            order_id=order.id,
            product_id=product.id,
            variation_id=variation.id,
            quantity=1,
            bonus_quantity=0,
            unit_price=25_000,
            subtotal=25_000,
        )
        session.add(order_item)

        session.commit()
    finally:
        session.close()

    service_session = session_factory()
    try:
        service = PreUploadedService(service_session)

        # First delivery invocation
        result1 = service.deliver_order("ORD_REENTRANT_01")
        assert result1 is not None
        assert result1["success"] is True
        assert len(result1["products"]) == 1
        delivered_id_1 = result1["products"][0]["id"]
        assert delivered_id_1 in ["stock_001", "stock_002", "stock_003"]

        # Check stock state after first delivery: exactly 1 used, 2 unused
        unused_after_first = (
            service_session.execute(
                select(PreUploadedProduct).where(
                    PreUploadedProduct.variation_id == "var_reentrant_01",
                    PreUploadedProduct.is_used.is_(False),
                )
            )
            .scalars()
            .all()
        )
        assert len(unused_after_first) == 2

        # Second delivery invocation (re-entrant call on the same order)
        result2 = service.deliver_order("ORD_REENTRANT_01")
        assert result2 is not None
        assert result2["success"] is True
        assert len(result2["products"]) == 1
        delivered_id_2 = result2["products"][0]["id"]

        # Must return the SAME item, not allocate a second one
        assert delivered_id_2 == delivered_id_1

        # Check stock state after second delivery: STILL exactly 2 unused!
        unused_after_second = (
            service_session.execute(
                select(PreUploadedProduct).where(
                    PreUploadedProduct.variation_id == "var_reentrant_01",
                    PreUploadedProduct.is_used.is_(False),
                )
            )
            .scalars()
            .all()
        )
        assert len(unused_after_second) == 2
        unused_ids = [p.id for p in unused_after_second]
        assert delivered_id_1 not in unused_ids
    finally:
        service_session.close()


def test_deliver_order_nonexistent_returns_none(session_factory):
    session = session_factory()
    try:
        service = PreUploadedService(session)
        result = service.deliver_order("NONEXISTENT_ORDER_ID")
        assert result is None
    finally:
        session.close()
