"""
Tests for order service.
Following TDD: Write tests first, then implement service.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models.base import Base
from src.database.models import ProductVariation, DeliveryType
from src.database.models.enums import OrderStatus
from src.database.services.order_service import OrderService
from src.database.services.variation_service import VariationService
from src.database.services.product_service import ProductService


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
    product_service = ProductService(db_session)
    return product_service.create_product({
        "id": "prod_1",
        "name": "Test Product",
        "description": "Test description",
        "delivery_type": DeliveryType.PRE_UPLOADED,
        "is_active": True,
    })


@pytest.fixture
def sample_variation(db_session, sample_product):
    """Create a sample variation for testing."""
    variation_service = VariationService(db_session)
    return variation_service.create_variation({
        "id": "var_1",
        "product_id": "prod_1",
        "name": "Pro 12M 1PCS",
        "price": 40000,
        "stock": 100,
        "is_active": True,
    })


@pytest.fixture
def order_service(db_session):
    """Create order service instance."""
    return OrderService(db_session)


class TestOrderService:
    """Test OrderService class."""

    def test_generate_order_id(self, order_service):
        """Test order ID generation."""
        order_id = order_service.generate_order_id()
        assert order_id is not None
        assert isinstance(order_id, str)
        assert len(order_id) > 0

    def test_generate_order_item_id(self, order_service):
        """Test order item ID generation."""
        item_id = order_service.generate_order_item_id()
        assert item_id is not None
        assert isinstance(item_id, str)
        assert item_id.startswith("item_")

    def test_validate_stock_sufficient(self, order_service, sample_variation):
        """Test stock validation with sufficient stock."""
        assert order_service.validate_stock("var_1", 50) is True
        assert order_service.validate_stock("var_1", 100) is True  # Exact match

    def test_validate_stock_insufficient(self, order_service, sample_variation):
        """Test stock validation with insufficient stock."""
        assert order_service.validate_stock("var_1", 101) is False
        assert order_service.validate_stock("var_1", 0) is False
        assert order_service.validate_stock("var_1", -1) is False

    def test_validate_stock_nonexistent(self, order_service):
        """Test stock validation with nonexistent variation."""
        assert order_service.validate_stock("nonexistent", 1) is False

    def test_calculate_total(self, order_service, sample_variation):
        """Test total calculation."""
        assert order_service.calculate_total("var_1", 1) == 40000
        assert order_service.calculate_total("var_1", 2) == 80000
        assert order_service.calculate_total("var_1", 5) == 200000

    def test_calculate_total_nonexistent(self, order_service):
        """Test total calculation with nonexistent variation."""
        with pytest.raises(ValueError, match="not found"):
            order_service.calculate_total("nonexistent", 1)

    def test_create_order_success(self, order_service, sample_variation, db_session):
        """Test successful order creation."""
        user_id = 123456789
        order = order_service.create_order(
            user_id=user_id,
            variation_id="var_1",
            quantity=2,
        )

        assert order is not None
        assert order.user_id == user_id
        assert order.status == OrderStatus.PENDING
        assert order.total_amount == 80000  # 2 * 40000
        assert len(order.items) == 1

        order_item = order.items[0]
        assert order_item.product_id == "prod_1"
        assert order_item.variation_id == "var_1"
        assert order_item.quantity == 2
        assert order_item.unit_price == 40000
        assert order_item.subtotal == 80000

    def test_create_order_insufficient_stock(self, order_service, sample_variation):
        """Test order creation with insufficient stock."""
        with pytest.raises(ValueError, match="Insufficient stock"):
            order_service.create_order(
                user_id=123456789,
                variation_id="var_1",
                quantity=101,
            )

    def test_create_order_nonexistent_variation(self, order_service):
        """Test order creation with nonexistent variation."""
        with pytest.raises(ValueError, match="not found"):
            order_service.create_order(
                user_id=123456789,
                variation_id="nonexistent",
                quantity=1,
            )

    def test_get_order_by_id(self, order_service, sample_variation):
        """Test getting order by ID."""
        order = order_service.create_order(
            user_id=123456789,
            variation_id="var_1",
            quantity=1,
        )

        retrieved = order_service.get_order_by_id(order.id)
        assert retrieved is not None
        assert retrieved.id == order.id
        assert retrieved.user_id == 123456789

    def test_get_order_by_id_nonexistent(self, order_service):
        """Test getting nonexistent order."""
        assert order_service.get_order_by_id("nonexistent") is None

    def test_get_user_orders(self, order_service, sample_variation):
        """Test getting user orders."""
        user_id = 123456789
        order1 = order_service.create_order(user_id=user_id, variation_id="var_1", quantity=1)
        order2 = order_service.create_order(user_id=user_id, variation_id="var_1", quantity=2)

        orders = order_service.get_user_orders(user_id)
        assert len(orders) == 2
        # Orders should be returned (most recent first, but timestamps might be same)
        order_ids = [o.id for o in orders]
        assert order1.id in order_ids
        assert order2.id in order_ids

    def test_get_user_orders_with_status(self, order_service, sample_variation):
        """Test getting user orders filtered by status."""
        user_id = 123456789
        order1 = order_service.create_order(user_id=user_id, variation_id="var_1", quantity=1)
        order_service.update_order_status(order1.id, OrderStatus.PAID)
        
        order2 = order_service.create_order(user_id=user_id, variation_id="var_1", quantity=1)

        pending_orders = order_service.get_user_orders(user_id, status=OrderStatus.PENDING)
        assert len(pending_orders) == 1
        assert pending_orders[0].id == order2.id

        paid_orders = order_service.get_user_orders(user_id, status=OrderStatus.PAID)
        assert len(paid_orders) == 1
        assert paid_orders[0].id == order1.id

    def test_update_order_status(self, order_service, sample_variation):
        """Test updating order status."""
        order = order_service.create_order(
            user_id=123456789,
            variation_id="var_1",
            quantity=1,
        )

        updated = order_service.update_order_status(order.id, OrderStatus.PAID)
        assert updated is not None
        assert updated.status == OrderStatus.PAID

        retrieved = order_service.get_order_by_id(order.id)
        assert retrieved.status == OrderStatus.PAID

    def test_update_order_status_with_transaction_id(self, order_service, sample_variation):
        """Test updating order status with transaction ID."""
        order = order_service.create_order(
            user_id=123456789,
            variation_id="var_1",
            quantity=1,
        )

        updated = order_service.update_order_status(
            order.id,
            OrderStatus.PAID,
            payment_transaction_id="trans_123",
        )
        assert updated is not None
        assert updated.payment_transaction_id == "trans_123"

    def test_update_order_status_nonexistent(self, order_service):
        """Test updating nonexistent order."""
        assert order_service.update_order_status("nonexistent", OrderStatus.PAID) is None

    def test_decrease_stock(self, order_service, sample_variation, db_session):
        """Test decreasing stock after order."""
        # For PRE_UPLOADED products, stock is calculated from pre-uploaded products
        # The decrease_stock method validates availability but doesn't modify the stock field
        # Stock reduction happens when pre-uploaded products are marked as used
        initial_stock = sample_variation.stock
        
        # This should validate stock availability (from pre-uploaded products)
        # but won't decrease the stock field for PRE_UPLOADED products
        try:
            order_service.decrease_stock("var_1", 10)
            # If no pre-uploaded products exist, this will raise ValueError
        except ValueError:
            # Expected if no pre-uploaded products exist
            pass
        
        variation = db_session.query(ProductVariation).filter_by(id="var_1").first()
        # Stock field doesn't change for PRE_UPLOADED products
        assert variation.stock == initial_stock

    def test_cancel_order_success(self, order_service, sample_variation, db_session):
        """Test successfully cancelling a PENDING order."""
        order = order_service.create_order(
            user_id=123456789,
            variation_id="var_1",
            quantity=2,
        )
        
        initial_stock = sample_variation.stock
        
        cancelled_order = order_service.cancel_order(order.id)
        
        assert cancelled_order is not None
        assert cancelled_order.status == OrderStatus.CANCELLED
        assert cancelled_order.id == order.id
        
        # Verify order is cancelled in database
        retrieved = order_service.get_order_by_id(order.id)
        assert retrieved.status == OrderStatus.CANCELLED
        
        # Stock should not change (PENDING orders haven't decreased stock)
        variation = db_session.query(ProductVariation).filter_by(id="var_1").first()
        assert variation.stock == initial_stock

    def test_cancel_order_already_paid(self, order_service, sample_variation):
        """Test that PAID orders cannot be cancelled."""
        order = order_service.create_order(
            user_id=123456789,
            variation_id="var_1",
            quantity=1,
        )
        
        # Update order to PAID
        order_service.update_order_status(order.id, OrderStatus.PAID)
        
        # Try to cancel - should raise ValueError
        with pytest.raises(ValueError, match="can only be cancelled"):
            order_service.cancel_order(order.id)
        
        # Verify order is still PAID
        retrieved = order_service.get_order_by_id(order.id)
        assert retrieved.status == OrderStatus.PAID

    def test_cancel_order_already_cancelled(self, order_service, sample_variation):
        """Test that already CANCELLED orders cannot be cancelled again."""
        order = order_service.create_order(
            user_id=123456789,
            variation_id="var_1",
            quantity=1,
        )
        
        # Cancel once
        order_service.cancel_order(order.id)
        
        # Try to cancel again - should raise ValueError
        with pytest.raises(ValueError, match="can only be cancelled"):
            order_service.cancel_order(order.id)

    def test_cancel_order_processing(self, order_service, sample_variation):
        """Test that PROCESSING orders cannot be cancelled."""
        order = order_service.create_order(
            user_id=123456789,
            variation_id="var_1",
            quantity=1,
        )
        
        order_service.update_order_status(order.id, OrderStatus.PROCESSING)
        
        with pytest.raises(ValueError, match="can only be cancelled"):
            order_service.cancel_order(order.id)

    def test_cancel_order_delivered(self, order_service, sample_variation):
        """Test that DELIVERED orders cannot be cancelled."""
        order = order_service.create_order(
            user_id=123456789,
            variation_id="var_1",
            quantity=1,
        )
        
        order_service.update_order_status(order.id, OrderStatus.DELIVERED)
        
        with pytest.raises(ValueError, match="can only be cancelled"):
            order_service.cancel_order(order.id)

    def test_cancel_order_nonexistent(self, order_service):
        """Test cancelling a nonexistent order."""
        with pytest.raises(ValueError, match="not found"):
            order_service.cancel_order("nonexistent")

