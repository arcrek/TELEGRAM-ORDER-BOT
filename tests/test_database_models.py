"""
Tests for database models.
Following TDD: Write tests first, then implement models.
"""
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import (
    Base,
    Order,
    OrderItem,
    PreUploadedProduct,
    Product,
    ProductVariation,
    Supplier,
    SupplierOrder,
)
from src.database.models.enums import DeliveryType, OrderStatus, SupplierOrderStatus


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestProduct:
    """Test Product model."""

    def test_create_product(self, db_session):
        """Test creating a product."""
        product = Product(
            id="prod_1",
            name="Test Product",
            description="Test description",
            delivery_type=DeliveryType.PRE_UPLOADED,
            is_active=True,
        )
        db_session.add(product)
        db_session.commit()

        retrieved = db_session.query(Product).filter_by(id="prod_1").first()
        assert retrieved is not None
        assert retrieved.name == "Test Product"
        assert retrieved.description == "Test description"
        assert retrieved.delivery_type == DeliveryType.PRE_UPLOADED
        assert retrieved.is_active is True
        assert isinstance(retrieved.created_at, datetime)
        assert isinstance(retrieved.updated_at, datetime)

    def test_product_relationships(self, db_session):
        """Test product relationships with variations."""
        product = Product(
            id="prod_1",
            name="Test Product",
            description="Test description",
            delivery_type=DeliveryType.PRE_UPLOADED,
            is_active=True,
        )
        variation = ProductVariation(
            id="var_1",
            product_id="prod_1",
            name="Variation 1",
            price=10000,
            stock=100,
            is_active=True,
        )
        db_session.add(product)
        db_session.add(variation)
        db_session.commit()

        retrieved = db_session.query(Product).filter_by(id="prod_1").first()
        assert len(retrieved.variations) == 1
        assert retrieved.variations[0].name == "Variation 1"


class TestProductVariation:
    """Test ProductVariation model."""

    def test_create_variation(self, db_session):
        """Test creating a product variation."""
        product = Product(
            id="prod_1",
            name="Test Product",
            description="Test description",
            delivery_type=DeliveryType.PRE_UPLOADED,
            is_active=True,
        )
        variation = ProductVariation(
            id="var_1",
            product_id="prod_1",
            name="Pro 12M 1PCS",
            price=40000,
            stock=51,
            is_active=True,
        )
        db_session.add(product)
        db_session.add(variation)
        db_session.commit()

        retrieved = db_session.query(ProductVariation).filter_by(id="var_1").first()
        assert retrieved is not None
        assert retrieved.name == "Pro 12M 1PCS"
        assert retrieved.price == 40000
        assert retrieved.stock == 51
        assert retrieved.product_id == "prod_1"


class TestOrder:
    """Test Order model."""

    def test_create_order(self, db_session):
        """Test creating an order."""
        order = Order(
            id="order_1",
            user_id=123456789,
            status=OrderStatus.PENDING,
            total_amount=40000,
        )
        db_session.add(order)
        db_session.commit()

        retrieved = db_session.query(Order).filter_by(id="order_1").first()
        assert retrieved is not None
        assert retrieved.user_id == 123456789
        assert retrieved.status == OrderStatus.PENDING
        assert retrieved.total_amount == 40000
        assert retrieved.payment_transaction_id is None
        assert isinstance(retrieved.created_at, datetime)

    def test_order_with_items(self, db_session):
        """Test order relationships with order items."""
        product = Product(
            id="prod_1",
            name="Test Product",
            description="Test description",
            delivery_type=DeliveryType.PRE_UPLOADED,
            is_active=True,
        )
        variation = ProductVariation(
            id="var_1",
            product_id="prod_1",
            name="Variation 1",
            price=40000,
            stock=100,
            is_active=True,
        )
        order = Order(
            id="order_1",
            user_id=123456789,
            status=OrderStatus.PENDING,
            total_amount=40000,
        )
        order_item = OrderItem(
            id="item_1",
            order_id="order_1",
            product_id="prod_1",
            variation_id="var_1",
            quantity=1,
            unit_price=40000,
            subtotal=40000,
        )
        db_session.add_all([product, variation, order, order_item])
        db_session.commit()

        retrieved = db_session.query(Order).filter_by(id="order_1").first()
        assert len(retrieved.items) == 1
        assert retrieved.items[0].quantity == 1
        assert retrieved.items[0].subtotal == 40000


class TestPreUploadedProduct:
    """Test PreUploadedProduct model."""

    def test_create_pre_uploaded_product(self, db_session):
        """Test creating a pre-uploaded product."""
        product = Product(
            id="prod_1",
            name="Test Product",
            description="Test description",
            delivery_type=DeliveryType.PRE_UPLOADED,
            is_active=True,
        )
        variation = ProductVariation(
            id="var_1",
            product_id="prod_1",
            name="Variation 1",
            price=40000,
            stock=100,
            is_active=True,
        )
        pre_uploaded = PreUploadedProduct(
            id="pre_1",
            product_id="prod_1",
            variation_id="var_1",
            product_data='{"username": "test", "password": "pass123"}',
            is_used=False,
        )
        db_session.add_all([product, variation, pre_uploaded])
        db_session.commit()

        retrieved = db_session.query(PreUploadedProduct).filter_by(id="pre_1").first()
        assert retrieved is not None
        assert retrieved.product_id == "prod_1"
        assert retrieved.variation_id == "var_1"
        assert retrieved.is_used is False
        assert retrieved.used_at is None
        assert retrieved.used_by_order_id is None


class TestSupplier:
    """Test Supplier model."""

    def test_create_supplier(self, db_session):
        """Test creating a supplier."""
        supplier = Supplier(
            id="supp_1",
            telegram_user_id=1241761975,
            name="Test Supplier",
            is_active=True,
        )
        db_session.add(supplier)
        db_session.commit()

        retrieved = db_session.query(Supplier).filter_by(id="supp_1").first()
        assert retrieved is not None
        assert retrieved.telegram_user_id == 1241761975
        assert retrieved.name == "Test Supplier"
        assert retrieved.is_active is True


class TestSupplierOrder:
    """Test SupplierOrder model."""

    def test_create_supplier_order(self, db_session):
        """Test creating a supplier order."""
        supplier = Supplier(
            id="supp_1",
            telegram_user_id=1241761975,
            name="Test Supplier",
            is_active=True,
        )
        order = Order(
            id="order_1",
            user_id=123456789,
            status=OrderStatus.PAID,
            total_amount=40000,
        )
        supplier_order = SupplierOrder(
            id="so_1",
            order_id="order_1",
            supplier_id="supp_1",
            status=SupplierOrderStatus.PENDING,
        )
        db_session.add_all([supplier, order, supplier_order])
        db_session.commit()

        retrieved = db_session.query(SupplierOrder).filter_by(id="so_1").first()
        assert retrieved is not None
        assert retrieved.order_id == "order_1"
        assert retrieved.supplier_id == "supp_1"
        assert retrieved.status == SupplierOrderStatus.PENDING
        assert retrieved.notification_message_id is None
        assert retrieved.supplier_response_message_id is None

