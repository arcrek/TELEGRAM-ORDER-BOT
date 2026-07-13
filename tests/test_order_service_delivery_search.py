"""
Tests for order_service delivery-content and delivery-date search filters.

Covers:
- delivery_search (fuzzy/partial match on PreUploadedProduct.product_data)
- delivery_start_date / delivery_end_date (filter on PreUploadedProduct.used_at)
- get_total_count stays in lock-step with list_orders
- An order with multiple delivered rows is returned exactly once
- Non-matching fragment excludes the order
"""

import json
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.base import Base
from src.database.models.enums import OrderStatus, DeliveryType
from src.database.models.order import Order
from src.database.models.order_item import OrderItem
from src.database.models.product import Product
from src.database.models.product_variation import ProductVariation
from src.database.models.pre_uploaded_product import PreUploadedProduct
from src.database.services.order_service import OrderService


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    """In-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def order_service(db_session):
    return OrderService(db_session)


@pytest.fixture
def base_product(db_session):
    """PRE_UPLOADED product used for all delivery-search tests."""
    product = Product(
        id="dsprod_1",
        name="Delivery Search Product",
        description="Test",
        delivery_type=DeliveryType.PRE_UPLOADED,
        is_active=True,
    )
    db_session.add(product)
    db_session.commit()
    return product


@pytest.fixture
def base_variation(db_session, base_product):
    variation = ProductVariation(
        id="dsvar_1",
        product_id=base_product.id,
        name="Standard",
        price=50000,
        stock=10,
        is_active=True,
    )
    db_session.add(variation)
    db_session.commit()
    return variation


def _make_order(db_session, order_id: str) -> Order:
    """Helper: create a minimal PAID Order."""
    order = Order(
        id=order_id,
        user_id=99999,
        status=OrderStatus.PAID,
        total_amount=50000,
    )
    db_session.add(order)
    db_session.flush()
    return order


def _make_order_item(db_session, order_id: str, product_id: str, variation_id: str) -> OrderItem:
    item = OrderItem(
        id=f"item_{order_id}",
        order_id=order_id,
        product_id=product_id,
        variation_id=variation_id,
        quantity=1,
        unit_price=50000,
        subtotal=50000,
    )
    db_session.add(item)
    return item


def _make_pre_uploaded(
    db_session,
    pu_id: str,
    order_id: str,
    product_id: str,
    variation_id: str,
    product_data: str,
    used_at: datetime,
) -> PreUploadedProduct:
    pu = PreUploadedProduct(
        id=pu_id,
        product_id=product_id,
        variation_id=variation_id,
        product_data=product_data,
        is_used=True,
        used_by_order_id=order_id,
        used_at=used_at,
    )
    db_session.add(pu)
    return pu


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestDeliverySearch:
    """Tests for delivery_search param in list_orders / get_total_count."""

    def _seed_order_with_content(self, db_session, base_product, base_variation):
        """Seed one order whose delivered content contains 'secretkey123'."""
        order = _make_order(db_session, "ds_order_1")
        _make_order_item(db_session, "ds_order_1", base_product.id, base_variation.id)
        used_at = datetime(2026, 6, 15, 12, 0, 0)
        _make_pre_uploaded(
            db_session,
            "ds_pu_1",
            "ds_order_1",
            base_product.id,
            base_variation.id,
            json.dumps({"key": "secretkey123", "user": "alice"}),
            used_at,
        )
        db_session.commit()
        return order

    def test_matching_fragment_returns_order(self, order_service, db_session, base_product, base_variation):
        """delivery_search with a matching fragment includes the order."""
        self._seed_order_with_content(db_session, base_product, base_variation)
        results = order_service.list_orders(delivery_search="secretkey")
        ids = [o.id for o in results]
        assert "ds_order_1" in ids

    def test_non_matching_fragment_excludes_order(self, order_service, db_session, base_product, base_variation):
        """delivery_search with a non-matching fragment excludes the order."""
        self._seed_order_with_content(db_session, base_product, base_variation)
        results = order_service.list_orders(delivery_search="NOTHINGMATCHES_XYZ")
        ids = [o.id for o in results]
        assert "ds_order_1" not in ids

    def test_partial_match_works(self, order_service, db_session, base_product, base_variation):
        """Partial content match (substring) is sufficient."""
        self._seed_order_with_content(db_session, base_product, base_variation)
        results = order_service.list_orders(delivery_search="key123")
        ids = [o.id for o in results]
        assert "ds_order_1" in ids

    def test_count_matches_list_length_matching(self, order_service, db_session, base_product, base_variation):
        """get_total_count agrees with len(list_orders) when match exists."""
        self._seed_order_with_content(db_session, base_product, base_variation)
        results = order_service.list_orders(delivery_search="secretkey")
        count = order_service.get_total_count(delivery_search="secretkey")
        assert count == len(results)

    def test_count_matches_list_length_no_match(self, order_service, db_session, base_product, base_variation):
        """get_total_count agrees with len(list_orders) when no match."""
        self._seed_order_with_content(db_session, base_product, base_variation)
        results = order_service.list_orders(delivery_search="NOTHINGMATCHES_XYZ")
        count = order_service.get_total_count(delivery_search="NOTHINGMATCHES_XYZ")
        assert count == len(results)
        assert count == 0

    def test_order_with_multiple_delivered_rows_returned_once(
        self, order_service, db_session, base_product, base_variation
    ):
        """An order with 2 used pre_uploaded rows must appear exactly once in results."""
        _make_order(db_session, "ds_multi_1")
        _make_order_item(db_session, "ds_multi_1", base_product.id, base_variation.id)
        used_at = datetime(2026, 6, 15, 10, 0, 0)
        # Two delivered rows for the same order
        _make_pre_uploaded(
            db_session,
            "ds_pu_m1",
            "ds_multi_1",
            base_product.id,
            base_variation.id,
            json.dumps({"key": "multikey_alpha"}),
            used_at,
        )
        _make_pre_uploaded(
            db_session,
            "ds_pu_m2",
            "ds_multi_1",
            base_product.id,
            base_variation.id,
            json.dumps({"key": "multikey_beta"}),
            used_at,
        )
        db_session.commit()

        # Search matches both rows — order should appear exactly once
        results = order_service.list_orders(delivery_search="multikey")
        matched = [o for o in results if o.id == "ds_multi_1"]
        assert len(matched) == 1

        count = order_service.get_total_count(delivery_search="multikey")
        assert count == 1

    def test_unused_product_not_matched(self, order_service, db_session, base_product, base_variation):
        """is_used=False rows must NOT be matched even if content matches."""
        _make_order(db_session, "ds_unused_1")
        _make_order_item(db_session, "ds_unused_1", base_product.id, base_variation.id)
        pu = PreUploadedProduct(
            id="ds_unused_pu",
            product_id=base_product.id,
            variation_id=base_variation.id,
            product_data=json.dumps({"key": "unusedcontent_xyz"}),
            is_used=False,  # Not delivered
            used_by_order_id="ds_unused_1",
            used_at=None,
        )
        db_session.add(pu)
        db_session.commit()

        results = order_service.list_orders(delivery_search="unusedcontent_xyz")
        ids = [o.id for o in results]
        assert "ds_unused_1" not in ids


class TestDeliveryDateRange:
    """Tests for delivery_start_date / delivery_end_date filters."""

    def _seed_two_orders(self, db_session, base_product, base_variation):
        """
        Seed two orders with different delivery times:
          - ds_date_early: delivered 2026-01-10 12:00
          - ds_date_late:  delivered 2026-06-10 12:00
        """
        early_at = datetime(2026, 1, 10, 12, 0, 0)
        late_at = datetime(2026, 6, 10, 12, 0, 0)

        _make_order(db_session, "ds_date_early")
        _make_order_item(db_session, "ds_date_early", base_product.id, base_variation.id)
        _make_pre_uploaded(
            db_session, "ds_pu_early", "ds_date_early",
            base_product.id, base_variation.id,
            json.dumps({"key": "early_content"}), early_at,
        )

        _make_order(db_session, "ds_date_late")
        _make_order_item(db_session, "ds_date_late", base_product.id, base_variation.id)
        _make_pre_uploaded(
            db_session, "ds_pu_late", "ds_date_late",
            base_product.id, base_variation.id,
            json.dumps({"key": "late_content"}), late_at,
        )
        db_session.commit()

    def test_start_date_excludes_earlier(self, order_service, db_session, base_product, base_variation):
        """delivery_start_date filters out orders delivered before it."""
        self._seed_two_orders(db_session, base_product, base_variation)
        results = order_service.list_orders(delivery_start_date="2026-03-01T00:00:00")
        ids = [o.id for o in results]
        assert "ds_date_late" in ids
        assert "ds_date_early" not in ids

    def test_end_date_excludes_later(self, order_service, db_session, base_product, base_variation):
        """delivery_end_date filters out orders delivered after it."""
        self._seed_two_orders(db_session, base_product, base_variation)
        results = order_service.list_orders(delivery_end_date="2026-03-01T23:59:59")
        ids = [o.id for o in results]
        assert "ds_date_early" in ids
        assert "ds_date_late" not in ids

    def test_date_range_narrows_to_one(self, order_service, db_session, base_product, base_variation):
        """Start+end date range returns only the order within the window."""
        self._seed_two_orders(db_session, base_product, base_variation)
        results = order_service.list_orders(
            delivery_start_date="2026-05-01T00:00:00",
            delivery_end_date="2026-07-01T23:59:59",
        )
        ids = [o.id for o in results]
        assert "ds_date_late" in ids
        assert "ds_date_early" not in ids

    def test_count_matches_list_for_date_filter(self, order_service, db_session, base_product, base_variation):
        """get_total_count agrees with list_orders for date range filter."""
        self._seed_two_orders(db_session, base_product, base_variation)
        results = order_service.list_orders(delivery_start_date="2026-03-01T00:00:00")
        count = order_service.get_total_count(delivery_start_date="2026-03-01T00:00:00")
        assert count == len(results)

    def test_invalid_date_format_ignored(self, order_service, db_session, base_product, base_variation):
        """Unparseable date strings are silently ignored (no crash, no filter applied)."""
        self._seed_two_orders(db_session, base_product, base_variation)
        # With invalid dates, the filter is ignored — both orders visible (+ possibly others)
        results = order_service.list_orders(
            delivery_start_date="not-a-date",
            delivery_end_date="also-bad",
        )
        ids = [o.id for o in results]
        # Both seeded orders should still be present since the filter is ignored
        assert "ds_date_early" in ids
        assert "ds_date_late" in ids


class TestDeliveryCombinedFilters:
    """Tests combining delivery_search with delivery date range."""

    def test_content_and_date_combined(self, order_service, db_session, base_product, base_variation):
        """delivery_search AND delivery date range both applied (AND semantics)."""
        # Order A: matching content, early date
        _make_order(db_session, "ds_combo_a")
        _make_order_item(db_session, "ds_combo_a", base_product.id, base_variation.id)
        _make_pre_uploaded(
            db_session, "ds_pu_combo_a", "ds_combo_a",
            base_product.id, base_variation.id,
            json.dumps({"key": "combo_match"}),
            datetime(2026, 1, 5, 12, 0, 0),
        )

        # Order B: matching content, late date
        _make_order(db_session, "ds_combo_b")
        _make_order_item(db_session, "ds_combo_b", base_product.id, base_variation.id)
        _make_pre_uploaded(
            db_session, "ds_pu_combo_b", "ds_combo_b",
            base_product.id, base_variation.id,
            json.dumps({"key": "combo_match"}),
            datetime(2026, 6, 5, 12, 0, 0),
        )
        db_session.commit()

        # Filter: matching content + early date window
        results = order_service.list_orders(
            delivery_search="combo_match",
            delivery_start_date="2026-01-01T00:00:00",
            delivery_end_date="2026-03-01T23:59:59",
        )
        ids = [o.id for o in results]
        assert "ds_combo_a" in ids
        assert "ds_combo_b" not in ids

        count = order_service.get_total_count(
            delivery_search="combo_match",
            delivery_start_date="2026-01-01T00:00:00",
            delivery_end_date="2026-03-01T23:59:59",
        )
        assert count == len(results)

    def test_no_delivery_filter_no_exists_applied(self, order_service, db_session, base_product, base_variation):
        """When no delivery filter is set, orders WITHOUT pre-uploaded rows are still returned."""
        # Plain order with no pre-uploaded rows
        _make_order(db_session, "ds_plain_1")
        _make_order_item(db_session, "ds_plain_1", base_product.id, base_variation.id)
        db_session.commit()

        # No delivery filter — plain order must appear
        results = order_service.list_orders()
        ids = [o.id for o in results]
        assert "ds_plain_1" in ids
