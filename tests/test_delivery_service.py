"""
Tests for delivery service.
"""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.base import Base
from src.database.models.enums import DeliveryType, OrderStatus
from src.database.models.pre_uploaded_product import PreUploadedProduct
from src.database.models.product import Product
from src.database.models.product_variation import ProductVariation
from src.database.services.delivery_service import DeliveryService
from src.database.services.order_notification_service import OrderNotificationService
from src.database.services.order_service import OrderService
from src.ipn.processor import IPNOrderProcessor


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
def delivery_service(db_session):
    """Create a delivery service instance."""
    return DeliveryService(db_session)


@pytest.fixture
def sample_product_pre_uploaded(db_session):
    """Create a sample pre-uploaded product."""
    product = Product(
        id="prod_pre",
        name="Pre-uploaded Product",
        description="Test product",
        delivery_type=DeliveryType.PRE_UPLOADED,
        is_active=True,
    )
    db_session.add(product)
    db_session.commit()
    return product


@pytest.fixture
def sample_product_supplier(db_session):
    """Create a sample supplier-based product."""
    product = Product(
        id="prod_supp",
        name="Supplier Product",
        description="Test product",
        delivery_type=DeliveryType.SUPPLIER_BASED,
        is_active=True,
    )
    db_session.add(product)
    db_session.commit()
    return product


@pytest.fixture
def sample_variation_pre(db_session, sample_product_pre_uploaded):
    """Create a sample variation for pre-uploaded product with inventory rows."""
    variation = ProductVariation(
        id="var_pre",
        product_id=sample_product_pre_uploaded.id,
        name="Variation 1",
        price=100000,
        stock=10,
        is_active=True,
    )
    db_session.add(variation)
    db_session.commit()
    # Add inventory rows so actual stock > 0 (PRE_UPLOADED stock is counted from these)
    for i in range(10):
        item = PreUploadedProduct(
            id=f"pu_{i}",
            product_id=sample_product_pre_uploaded.id,
            variation_id="var_pre",
            product_data='{"key": "value"}',
            is_used=False,
        )
        db_session.add(item)
    db_session.commit()
    return variation


@pytest.fixture
def sample_variation_supp(db_session, sample_product_supplier):
    """Create a sample variation for supplier product."""
    variation = ProductVariation(
        id="var_supp",
        product_id=sample_product_supplier.id,
        name="Variation 1",
        price=200000,
        stock=5,
        is_active=True,
    )
    db_session.add(variation)
    db_session.commit()
    return variation


@pytest.mark.skip(reason="create_order for PRE_UPLOADED calls reserve_products_for_order which uses FOR UPDATE SKIP LOCKED, PostgreSQL only")
def test_get_order_delivery_type_pre_uploaded(
    db_session, delivery_service, sample_product_pre_uploaded, sample_variation_pre
):
    """Test getting delivery type for pre-uploaded order."""
    order_service = OrderService(db_session)
    order = order_service.create_order(
        user_id=123456789,
        variation_id=sample_variation_pre.id,
        quantity=1,
    )
    
    delivery_type = delivery_service.get_order_delivery_type(order.id)
    assert delivery_type == DeliveryType.PRE_UPLOADED


def test_get_order_delivery_type_supplier(
    db_session, delivery_service, sample_product_supplier, sample_variation_supp
):
    """Test getting delivery type for supplier-based order."""
    order_service = OrderService(db_session)
    order = order_service.create_order(
        user_id=123456789,
        variation_id=sample_variation_supp.id,
        quantity=1,
    )
    
    delivery_type = delivery_service.get_order_delivery_type(order.id)
    assert delivery_type == DeliveryType.SUPPLIER_BASED


def test_get_order_delivery_type_not_found(delivery_service):
    """Test getting delivery type for non-existent order."""
    delivery_type = delivery_service.get_order_delivery_type("nonexistent")
    assert delivery_type is None


@pytest.mark.skip(reason="create_order for PRE_UPLOADED calls reserve_products_for_order which uses FOR UPDATE SKIP LOCKED, PostgreSQL only")
def test_process_paid_order_pre_uploaded(
    db_session, delivery_service, sample_product_pre_uploaded, sample_variation_pre
):
    """Test processing paid order for pre-uploaded product."""
    order_service = OrderService(db_session)
    order = order_service.create_order(
        user_id=123456789,
        variation_id=sample_variation_pre.id,
        quantity=2,
    )
    
    # Verify initial status
    assert order.status == OrderStatus.PENDING
    
    # Process order
    success = delivery_service.process_paid_order(order.id)
    assert success is True
    
    # Verify order status updated
    updated_order = order_service.get_order_by_id(order.id)
    assert updated_order.status == OrderStatus.PROCESSING
    
    # For PRE_UPLOADED products, stock is calculated from pre-uploaded products
    # The stock field in the variation table doesn't change
    # Stock reduction happens when pre-uploaded products are marked as used
    db_session.refresh(sample_variation_pre)
    # Stock field remains unchanged (stock is managed via pre-uploaded products)
    assert sample_variation_pre.stock == 10  # Stock field doesn't change for PRE_UPLOADED


def test_process_paid_order_supplier(
    db_session, delivery_service, sample_product_supplier, sample_variation_supp
):
    """Test processing paid order for supplier-based product."""
    order_service = OrderService(db_session)
    order = order_service.create_order(
        user_id=123456789,
        variation_id=sample_variation_supp.id,
        quantity=1,
    )
    
    # Process order
    success = delivery_service.process_paid_order(order.id)
    assert success is True
    
    # Verify order status updated
    updated_order = order_service.get_order_by_id(order.id)
    assert updated_order.status == OrderStatus.PROCESSING
    
    # Verify stock decreased
    db_session.refresh(sample_variation_supp)
    assert sample_variation_supp.stock == 4  # 5 - 1


def test_process_paid_order_not_found(delivery_service):
    """Test processing non-existent order."""
    success = delivery_service.process_paid_order("nonexistent")
    assert success is False


def test_virtual_order_keeps_fixed_stock_and_sends_configured_content(
    db_session, delivery_service
):
    product = Product(
        id="prod_virtual",
        name="Virtual order",
        delivery_type=DeliveryType.VIRTUAL_ORDER,
        upgrade_request_text="Liên hệ hỗ trợ để nhận tài khoản: @support",
        is_active=True,
    )
    variation = ProductVariation(
        id="var_virtual",
        product_id=product.id,
        name="Default",
        price=10_000,
        stock=123,
        is_active=True,
    )
    db_session.add_all([product, variation])
    db_session.commit()

    order = OrderService(db_session).create_order(123456789, variation.id, 2)
    assert delivery_service.process_paid_order(order.id) is True
    db_session.refresh(variation)
    assert variation.stock == 123

    processor = IPNOrderProcessor.__new__(IPNOrderProcessor)
    processor.bot = AsyncMock()
    with patch.object(
        OrderNotificationService,
        "prepare_order_paid_notification",
        return_value=None,
    ):
        processor._handle_virtual_order_delivery(db_session, order.id, order.user_id)

    processor.bot.send_message.assert_awaited_once_with(
        chat_id=order.user_id,
        text="Liên hệ hỗ trợ để nhận tài khoản: @support",
    )
    assert OrderService(db_session).get_order_by_id(order.id).status == OrderStatus.DELIVERED
