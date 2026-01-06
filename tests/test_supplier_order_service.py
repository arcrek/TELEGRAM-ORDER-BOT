"""
Tests for supplier order service.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models.base import Base
from src.database.services.supplier_order_service import SupplierOrderService
from src.database.services.order_service import OrderService
from src.database.models.enums import DeliveryType, SupplierOrderStatus
from src.database.models.product import Product
from src.database.models.product_variation import ProductVariation
from src.database.models.supplier import Supplier


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
def supplier_order_service(db_session):
    """Create a supplier order service instance."""
    return SupplierOrderService(db_session)


@pytest.fixture
def sample_supplier(db_session):
    """Create a sample supplier."""
    supplier = Supplier(
        id="supp_1",
        telegram_user_id=987654321,
        name="Test Supplier",
        is_active=True,
    )
    db_session.add(supplier)
    db_session.commit()
    return supplier


@pytest.fixture
def sample_product(db_session):
    """Create a sample product."""
    product = Product(
        id="prod_test",
        name="Test Product",
        description="Test",
        delivery_type=DeliveryType.SUPPLIER_BASED,
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


def test_generate_supplier_order_id(supplier_order_service):
    """Test generating supplier order ID."""
    order_id = supplier_order_service.generate_supplier_order_id()
    assert order_id.startswith("supp_")
    assert len(order_id) > 8


def test_get_supplier_for_product(supplier_order_service, sample_supplier, sample_product):
    """Test getting supplier for a product."""
    supplier = supplier_order_service.get_supplier_for_product(sample_product.id)
    assert supplier is not None
    assert supplier.id == sample_supplier.id


def test_get_supplier_for_product_no_supplier(supplier_order_service, sample_product):
    """Test getting supplier when none exists."""
    supplier = supplier_order_service.get_supplier_for_product(sample_product.id)
    assert supplier is None


def test_create_supplier_order(
    db_session, supplier_order_service, sample_supplier, sample_product, sample_variation
):
    """Test creating a supplier order."""
    order_service = OrderService(db_session)
    order = order_service.create_order(
        user_id=123456789,
        variation_id=sample_variation.id,
        quantity=1,
    )
    
    supplier_order = supplier_order_service.create_supplier_order(
        order.id, sample_supplier.id
    )
    assert supplier_order is not None
    assert supplier_order.order_id == order.id
    assert supplier_order.supplier_id == sample_supplier.id
    assert supplier_order.status == SupplierOrderStatus.PENDING


def test_create_supplier_order_duplicate(
    db_session, supplier_order_service, sample_supplier, sample_product, sample_variation
):
    """Test creating duplicate supplier order."""
    order_service = OrderService(db_session)
    order = order_service.create_order(
        user_id=123456789,
        variation_id=sample_variation.id,
        quantity=1,
    )
    
    # Create first order
    supplier_order1 = supplier_order_service.create_supplier_order(
        order.id, sample_supplier.id
    )
    
    # Try to create duplicate
    supplier_order2 = supplier_order_service.create_supplier_order(
        order.id, sample_supplier.id
    )
    
    assert supplier_order1.id == supplier_order2.id


def test_create_supplier_orders_for_order(
    db_session, supplier_order_service, sample_supplier, sample_product, sample_variation
):
    """Test creating supplier orders for an order."""
    order_service = OrderService(db_session)
    order = order_service.create_order(
        user_id=123456789,
        variation_id=sample_variation.id,
        quantity=1,
    )
    
    supplier_orders = supplier_order_service.create_supplier_orders_for_order(order.id)
    assert len(supplier_orders) == 1
    assert supplier_orders[0].order_id == order.id
    assert supplier_orders[0].supplier_id == sample_supplier.id


def test_format_order_notification(
    db_session, supplier_order_service, sample_product, sample_variation
):
    """Test formatting order notification."""
    order_service = OrderService(db_session)
    order = order_service.create_order(
        user_id=123456789,
        variation_id=sample_variation.id,
        quantity=2,
    )
    
    message = supplier_order_service.format_order_notification(order.id)
    assert message is not None
    assert order.id in message
    assert str(order.user_id) in message
    # Check for formatted amount (with commas)
    assert f"{order.total_amount:,}" in message or str(order.total_amount) in message
    assert "Items:" in message


def test_format_order_notification_not_found(supplier_order_service):
    """Test formatting notification for non-existent order."""
    message = supplier_order_service.format_order_notification("nonexistent")
    assert message is None


def test_update_notification_message_id(
    db_session, supplier_order_service, sample_supplier, sample_product, sample_variation
):
    """Test updating notification message ID."""
    order_service = OrderService(db_session)
    order = order_service.create_order(
        user_id=123456789,
        variation_id=sample_variation.id,
        quantity=1,
    )
    
    supplier_order = supplier_order_service.create_supplier_order(
        order.id, sample_supplier.id
    )
    
    message_id = 12345
    updated = supplier_order_service.update_notification_message_id(
        supplier_order.id, message_id
    )
    assert updated is not None
    assert updated.notification_message_id == message_id


def test_get_supplier_order_by_id(
    db_session, supplier_order_service, sample_supplier, sample_product, sample_variation
):
    """Test getting supplier order by ID."""
    order_service = OrderService(db_session)
    order = order_service.create_order(
        user_id=123456789,
        variation_id=sample_variation.id,
        quantity=1,
    )
    
    supplier_order = supplier_order_service.create_supplier_order(
        order.id, sample_supplier.id
    )
    
    retrieved = supplier_order_service.get_supplier_order_by_id(supplier_order.id)
    assert retrieved is not None
    assert retrieved.id == supplier_order.id

