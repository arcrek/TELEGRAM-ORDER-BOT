"""Tests for the /export data service."""
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.base import Base
from src.database.models.enums import DeliveryType, OrderStatus
from src.database.models.order import Order
from src.database.models.order_item import OrderItem
from src.database.models.pre_uploaded_product import PreUploadedProduct
from src.database.models.product import Product
from src.database.models.product_variation import ProductVariation
from src.database.services.export_service import ExportService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _seed_delivered_order(session, *, order_id, user_id, product_id, variation_id,
                          subtotal, quantity, bonus, contents, created_at):
    """Create a DELIVERED order with one item and `len(contents)` used rows."""
    session.add(Order(id=order_id, user_id=user_id, status=OrderStatus.DELIVERED,
                       total_amount=subtotal, created_at=created_at))
    session.add(OrderItem(id=f"oi_{order_id}", order_id=order_id, product_id=product_id,
                          variation_id=variation_id, quantity=quantity, bonus_quantity=bonus,
                          unit_price=subtotal, subtotal=subtotal))
    for i, c in enumerate(contents):
        session.add(PreUploadedProduct(
            id=f"pu_{order_id}_{i}", product_id=product_id, variation_id=variation_id,
            product_data=c, is_used=True, used_by_order_id=order_id, used_at=created_at))
    session.commit()


@pytest.fixture
def seeded(db_session):
    s = db_session
    s.add(Product(id="p1", name="Netflix", delivery_type=DeliveryType.PRE_UPLOADED, is_active=True))
    s.add(Product(id="p2", name="Spotify", delivery_type=DeliveryType.PRE_UPLOADED, is_active=True))
    s.add(ProductVariation(id="v1", product_id="p1", name="1 Month", price=90000, stock=5))
    s.add(ProductVariation(id="v2", product_id="p1", name="12 Month", price=900000, stock=5))
    s.add(ProductVariation(id="v3", product_id="p2", name="Premium", price=50000, stock=5))
    s.commit()
    # User 100: two delivered orders of p1/v1, one of p1/v2, one of p2/v3.
    _seed_delivered_order(s, order_id="o1", user_id=100, product_id="p1", variation_id="v1",
                          subtotal=90000, quantity=1, bonus=0, contents=["acc1@mail|x"],
                          created_at=datetime(2026, 6, 1, 7, 30))
    _seed_delivered_order(s, order_id="o2", user_id=100, product_id="p1", variation_id="v1",
                          subtotal=270000, quantity=3, bonus=0,
                          contents=["acc2@mail|x", "acc3@mail|x", "acc4@mail|x"],
                          created_at=datetime(2026, 6, 10, 2, 12))
    _seed_delivered_order(s, order_id="o3", user_id=100, product_id="p1", variation_id="v2",
                          subtotal=900000, quantity=1, bonus=0, contents=["acc5@mail|x"],
                          created_at=datetime(2026, 6, 11, 0, 0))
    _seed_delivered_order(s, order_id="o4", user_id=100, product_id="p2", variation_id="v3",
                          subtotal=50000, quantity=1, bonus=0, contents=["acc6@mail|x"],
                          created_at=datetime(2026, 6, 12, 0, 0))
    # Another user's delivered order — MUST NEVER leak into user 100's export.
    _seed_delivered_order(s, order_id="o5", user_id=999, product_id="p1", variation_id="v1",
                          subtotal=90000, quantity=1, bonus=0, contents=["OTHERUSER@mail|x"],
                          created_at=datetime(2026, 6, 1, 0, 0))
    # A PAID-but-not-delivered order — MUST be excluded (status filter).
    s.add(Order(id="o6", user_id=100, status=OrderStatus.PAID, total_amount=90000,
                created_at=datetime(2026, 6, 13, 0, 0)))
    s.add(PreUploadedProduct(id="pu_o6_0", product_id="p1", variation_id="v1",
                             product_data="NOTDELIVERED@mail|x", is_used=False,
                             used_by_order_id="o6"))
    s.commit()
    return s


def test_exportable_products_are_distinct_and_user_scoped(seeded):
    svc = ExportService(seeded)
    products = svc.get_exportable_products(100)
    assert [p["name"] for p in products] == ["Netflix", "Spotify"]  # sorted, distinct
    ids = {p["id"] for p in products}
    assert ids == {"p1", "p2"}


def test_exportable_products_excludes_other_users(seeded):
    svc = ExportService(seeded)
    assert svc.get_exportable_products(999) == [{"id": "p1", "name": "Netflix"}]


def test_exportable_variations(seeded):
    svc = ExportService(seeded)
    variations = svc.get_exportable_variations(100, "p1")
    assert [v["name"] for v in variations] == ["1 Month", "12 Month"]


def test_variant_export_groups_orders_and_counts_items(seeded):
    svc = ExportService(seeded)
    data = svc.get_variant_export(100, "p1", "v1")
    assert data is not None
    assert data.product_name == "Netflix"
    assert data.variation_name == "1 Month"
    assert data.total_orders == 2          # o1 + o2
    assert data.total_items == 4           # 1 + 3 delivered rows
    o1, o2 = data.orders                    # ordered by created_at
    assert o1.order_id == "o1" and o1.contents == ["acc1@mail|x"]
    assert o2.order_id == "o2" and len(o2.contents) == 3
    assert o2.price == 270000 and o2.quantity == 3


def test_variant_export_does_not_leak_other_variant(seeded):
    svc = ExportService(seeded)
    data = svc.get_variant_export(100, "p1", "v1")
    flat = [c for o in data.orders for c in o.contents]
    assert "acc5@mail|x" not in flat        # that belongs to v2
    assert "OTHERUSER@mail|x" not in flat    # belongs to user 999
    assert "NOTDELIVERED@mail|x" not in flat # belongs to PAID order o6


def test_variant_export_none_when_empty(seeded):
    svc = ExportService(seeded)
    assert svc.get_variant_export(100, "p1", "nonexistent") is None
