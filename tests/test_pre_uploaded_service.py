"""
Tests for pre-uploaded product service.
"""

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.base import Base
from src.database.models.enums import DeliveryType
from src.database.models.pre_uploaded_product import PreUploadedProduct
from src.database.models.product import Product
from src.database.models.product_variation import ProductVariation
from src.database.services.order_service import OrderService
from src.database.services.pre_uploaded_service import PreUploadedService


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
def pre_uploaded_service(db_session):
    """Create a pre-uploaded service instance."""
    return PreUploadedService(db_session)


@pytest.fixture
def sample_product(db_session):
    """Create a sample product."""
    product = Product(
        id="prod_test",
        name="Test Product",
        description="Test",
        delivery_type=DeliveryType.PRE_UPLOADED,
        is_active=True,
    )
    db_session.add(product)
    db_session.commit()
    return product


@pytest.fixture
def sample_variation(db_session, sample_product):
    """Create a sample variation."""
    variation = ProductVariation(
        id="var_test",
        product_id=sample_product.id,
        name="Variation 1",
        price=100000,
        stock=10,
        is_active=True,
    )
    db_session.add(variation)
    db_session.commit()
    return variation


@pytest.fixture
def sample_pre_uploaded_products(db_session, sample_product, sample_variation):
    """Create sample pre-uploaded products."""
    products = []
    for i in range(3):
        product_data = {"username": f"user{i}", "password": f"pass{i}"}
        pre_product = PreUploadedProduct(
            id=f"pre_{i}",
            product_id=sample_product.id,
            variation_id=sample_variation.id,
            product_data=json.dumps(product_data),
            is_used=False,
        )
        db_session.add(pre_product)
        products.append(pre_product)
    db_session.commit()
    return products


def test_get_available_product(
    pre_uploaded_service, sample_variation, sample_pre_uploaded_products
):
    """Test getting an available pre-uploaded product."""
    product = pre_uploaded_service.get_available_product(sample_variation.id)
    assert product is not None
    assert product.is_used is False
    assert product.variation_id == sample_variation.id


def test_get_available_product_none(pre_uploaded_service):
    """Test getting available product when none exists."""
    product = pre_uploaded_service.get_available_product("nonexistent")
    assert product is None


def test_get_available_products(
    pre_uploaded_service, sample_variation, sample_pre_uploaded_products
):
    """Test getting multiple available products."""
    products = pre_uploaded_service.get_available_products(
        sample_variation.id, quantity=2
    )
    assert len(products) == 2
    assert all(p.is_used is False for p in products)


def test_mark_product_as_used(
    db_session, pre_uploaded_service, sample_pre_uploaded_products
):
    """Test marking a product as used."""
    product = sample_pre_uploaded_products[0]
    order_id = "order_123"

    marked = pre_uploaded_service.mark_product_as_used(product.id, order_id)
    assert marked is not None
    assert marked.is_used is True
    assert marked.used_by_order_id == order_id
    assert marked.used_at is not None


def test_mark_product_as_used_already_used(
    db_session, pre_uploaded_service, sample_pre_uploaded_products
):
    """Test marking an already used product."""
    product = sample_pre_uploaded_products[0]
    product.is_used = True
    db_session.commit()

    marked = pre_uploaded_service.mark_product_as_used(product.id, "order_123")
    assert marked is None


def test_get_product_data(pre_uploaded_service, sample_pre_uploaded_products):
    """Test getting product data."""
    product = sample_pre_uploaded_products[0]
    data = pre_uploaded_service.get_product_data(product)
    assert isinstance(data, dict)
    assert "username" in data
    assert "password" in data


@pytest.mark.skip(reason="reserve_products_for_order uses FOR UPDATE SKIP LOCKED, PostgreSQL only")
def test_deliver_order_success(
    db_session,
    pre_uploaded_service,
    sample_product,
    sample_variation,
    sample_pre_uploaded_products,
):
    """Test successful order delivery."""
    order_service = OrderService(db_session)
    order = order_service.create_order(
        user_id=123456789,
        variation_id=sample_variation.id,
        quantity=2,
    )

    result = pre_uploaded_service.deliver_order(order.id)
    assert result is not None
    assert result["success"] is True
    assert len(result["products"]) == 2
    assert len(result["failed_items"]) == 0

    # Verify products marked as used
    for product_data in result["products"]:
        product_id = product_data["id"]
        product = db_session.query(PreUploadedProduct).filter_by(id=product_id).first()
        assert product.is_used is True
        assert product.used_by_order_id == order.id


@pytest.mark.skip(reason="create_order calls reserve_products_for_order which uses FOR UPDATE SKIP LOCKED, PostgreSQL only")
def test_deliver_order_insufficient_products(
    db_session, pre_uploaded_service, sample_product, sample_variation
):
    """Test order delivery with insufficient products."""
    # Create only 1 pre-uploaded product
    product_data = {"username": "user1", "password": "pass1"}
    pre_product = PreUploadedProduct(
        id="pre_1",
        product_id=sample_product.id,
        variation_id=sample_variation.id,
        product_data=json.dumps(product_data),
        is_used=False,
    )
    db_session.add(pre_product)
    db_session.commit()

    order_service = OrderService(db_session)
    order = order_service.create_order(
        user_id=123456789,
        variation_id=sample_variation.id,
        quantity=3,  # Request 3 but only 1 available
    )

    result = pre_uploaded_service.deliver_order(order.id)
    assert result is not None
    assert result["success"] is False
    assert len(result["failed_items"]) > 0


# ── export_available_products tests ──────────────────────────────────────────


def test_export_marks_sold_not_deleted(
    db_session, pre_uploaded_service, sample_pre_uploaded_products
):
    """Exported rows stay in DB with is_used=True and used_at set; used_by_order_id=None."""
    pre_product = sample_pre_uploaded_products[0]
    product_id = pre_product.product_id
    variation_id = pre_product.variation_id

    exported = pre_uploaded_service.export_available_products(
        product_id, variation_id, 1
    )

    assert len(exported) == 1
    row = db_session.query(PreUploadedProduct).filter_by(id=exported[0].id).first()
    assert row is not None, "Row must not be deleted"
    assert row.is_used is True
    assert row.used_at is not None
    assert row.used_by_order_id is None  # admin export, no order


def test_export_short_stock(
    db_session, pre_uploaded_service, sample_product, sample_variation
):
    """Request 5 with only 3 available → returns all 3, not an error."""
    for i in range(3):
        db_session.add(
            PreUploadedProduct(
                id=f"exp_short_{i}",
                product_id=sample_product.id,
                variation_id=sample_variation.id,
                product_data=f"data_{i}",
                is_used=False,
            )
        )
    db_session.commit()

    exported = pre_uploaded_service.export_available_products(
        sample_product.id, sample_variation.id, 5
    )

    assert len(exported) == 3


def test_export_oldest_first(
    db_session, pre_uploaded_service, sample_product, sample_variation
):
    """Oldest rows (by created_at) are exported first."""
    from datetime import timedelta

    base_dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # Insert in reverse order (newest first) so insertion order != creation order
    for i in reversed(range(3)):
        db_session.add(
            PreUploadedProduct(
                id=f"exp_ord_{i}",
                product_id=sample_product.id,
                variation_id=sample_variation.id,
                product_data=f"item_{i}",
                is_used=False,
                created_at=(base_dt + timedelta(days=i)).replace(tzinfo=None),
            )
        )
    db_session.commit()

    exported = pre_uploaded_service.export_available_products(
        sample_product.id, sample_variation.id, 2
    )

    assert len(exported) == 2
    # The two oldest rows should have been picked
    exported_data = {p.product_data for p in exported}
    assert "item_0" in exported_data
    assert "item_1" in exported_data
    assert "item_2" not in exported_data


def test_export_zero_available(
    db_session, pre_uploaded_service, sample_product, sample_variation
):
    """Zero available rows → empty list returned (not an exception)."""
    exported = pre_uploaded_service.export_available_products(
        sample_product.id, sample_variation.id, 5
    )
    assert exported == []


def test_export_respects_reserved(
    db_session, pre_uploaded_service, sample_product, sample_variation
):
    """Rows reserved by an order are NOT included in exports."""
    db_session.add(
        PreUploadedProduct(
            id="exp_res_1",
            product_id=sample_product.id,
            variation_id=sample_variation.id,
            product_data="reserved_data",
            is_used=False,
            reserved_by_order_id="order_xyz",
        )
    )
    db_session.add(
        PreUploadedProduct(
            id="exp_res_2",
            product_id=sample_product.id,
            variation_id=sample_variation.id,
            product_data="free_data",
            is_used=False,
            reserved_by_order_id=None,
        )
    )
    db_session.commit()

    exported = pre_uploaded_service.export_available_products(
        sample_product.id, sample_variation.id, 10
    )

    assert len(exported) == 1
    assert exported[0].product_data == "free_data"


def test_export_product_variation_filter(
    db_session, pre_uploaded_service, sample_product, sample_variation
):
    """Filter applies to both product_id and variation_id; a mismatch returns 0 rows."""
    exported = pre_uploaded_service.export_available_products(
        sample_product.id, "wrong_variation_id", 10
    )
    assert exported == []

    exported2 = pre_uploaded_service.export_available_products(
        "wrong_product_id", sample_variation.id, 10
    )
    assert exported2 == []
