"""
Tests for statistics service.
"""
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from src.database.connection import create_engine_instance, get_session_factory, init_database
from src.database.models import Order, OrderItem, Product, ProductVariation
from src.database.models.enums import OrderStatus, DeliveryType
from src.database.services.statistics_service import StatisticsService


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine_instance("sqlite:///:memory:")
    init_database(engine)
    session_factory = get_session_factory(engine)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def sample_products(db_session: Session):
    """Create sample products for testing."""
    products = []
    for i in range(5):  # Create 5 products to match 5 orders
        product = Product(
            id=f"prod_{i}",
            name=f"Product {i}",
            description=f"Description {i}",
            delivery_type=DeliveryType.PRE_UPLOADED,
            is_active=True,
        )
        db_session.add(product)
        products.append(product)
    
    db_session.commit()
    return products


@pytest.fixture
def sample_variations(db_session: Session, sample_products):
    """Create sample variations for testing."""
    variations = []
    for i, product in enumerate(sample_products):
        variation = ProductVariation(
            id=f"var_{i}",
            product_id=product.id,
            name=f"Variation {i}",
            price=10000 * (i + 1),  # 10k, 20k, 30k, 40k, 50k
            stock=100,
            is_active=True,
        )
        db_session.add(variation)
        variations.append(variation)
    
    db_session.commit()
    return variations


@pytest.fixture
def sample_orders(db_session: Session, sample_products, sample_variations):
    """Create sample orders for testing."""
    now = datetime.now(timezone.utc)
    orders = []
    
    # Create orders with different statuses and dates
    statuses = [
        OrderStatus.PENDING,
        OrderStatus.PAID,
        OrderStatus.DELIVERED,
        OrderStatus.DELIVERED,
        OrderStatus.CANCELLED,
    ]
    
    for i, (status, variation) in enumerate(zip(statuses, sample_variations)):
        # Create orders at different times
        created_at = now - timedelta(days=i)
        
        order = Order(
            id=f"order_{i}",
            user_id=123456789 + i,
            status=status,
            total_amount=variation.price * (i + 1),
            created_at=created_at,
        )
        db_session.add(order)
        
        # Create order item
        order_item = OrderItem(
            id=f"item_{i}",
            order_id=order.id,
            product_id=variation.product_id,
            variation_id=variation.id,
            quantity=i + 1,
            unit_price=variation.price,
            subtotal=variation.price * (i + 1),
        )
        db_session.add(order_item)
        orders.append(order)
    
    db_session.commit()
    return orders


class TestStatisticsService:
    """Test statistics service."""
    
    def test_get_total_orders_count_all_time(self, db_session: Session, sample_orders):
        """Test getting total orders count for all time."""
        service = StatisticsService(db_session)
        count = service.get_total_orders_count()
        assert count == 5
    
    def test_get_total_orders_count_today(self, db_session: Session, sample_orders):
        """Test getting total orders count for today."""
        service = StatisticsService(db_session)
        count = service.get_total_orders_count(period="today")
        # Only the most recent order (order_0) should be today
        assert count == 1
    
    def test_get_total_orders_count_this_week(self, db_session: Session, sample_orders):
        """Test getting total orders count for this week."""
        service = StatisticsService(db_session)
        count = service.get_total_orders_count(period="this_week")
        # All orders created within last 7 days
        assert count == 5
    
    def test_get_total_orders_count_this_month(self, db_session: Session, sample_orders):
        """Test getting total orders count for this month."""
        service = StatisticsService(db_session)
        count = service.get_total_orders_count(period="this_month")
        # All orders created within last 30 days
        assert count == 5
    
    def test_get_total_revenue_all_time(self, db_session: Session, sample_orders):
        """Test getting total revenue for all time."""
        service = StatisticsService(db_session)
        revenue = service.get_total_revenue()
        # Sum of all order amounts: 10k + 40k + 90k + 160k + 250k = 550k
        # But only PAID and DELIVERED orders count: 40k + 90k + 160k = 290k
        assert revenue == 290000
    
    def test_get_total_revenue_by_period(self, db_session: Session, sample_orders):
        """Test getting total revenue by period."""
        service = StatisticsService(db_session)
        revenue = service.get_total_revenue(period="today")
        # Only today's orders that are paid/delivered
        assert revenue >= 0
    
    def test_get_orders_by_status(self, db_session: Session, sample_orders):
        """Test getting orders grouped by status."""
        service = StatisticsService(db_session)
        status_counts = service.get_orders_by_status()
        
        # The method returns status.value (string) as keys
        assert status_counts[OrderStatus.PENDING.value] == 1
        assert status_counts[OrderStatus.PAID.value] == 1
        assert status_counts[OrderStatus.DELIVERED.value] == 2
        assert status_counts[OrderStatus.CANCELLED.value] == 1
    
    def test_get_orders_by_product(self, db_session: Session, sample_orders):
        """Test getting orders grouped by product."""
        service = StatisticsService(db_session)
        product_counts = service.get_orders_by_product()
        
        # Should have counts for each product
        assert len(product_counts) > 0
    
    def test_get_revenue_over_time_daily(self, db_session: Session, sample_orders):
        """Test getting revenue over time (daily)."""
        service = StatisticsService(db_session)
        revenue_data = service.get_revenue_over_time(interval="daily")
        
        assert isinstance(revenue_data, list)
        assert len(revenue_data) > 0
    
    def test_get_revenue_over_time_weekly(self, db_session: Session, sample_orders):
        """Test getting revenue over time (weekly)."""
        service = StatisticsService(db_session)
        revenue_data = service.get_revenue_over_time(interval="weekly")
        
        assert isinstance(revenue_data, list)
    
    def test_get_revenue_over_time_monthly(self, db_session: Session, sample_orders):
        """Test getting revenue over time (monthly)."""
        service = StatisticsService(db_session)
        revenue_data = service.get_revenue_over_time(interval="monthly")
        
        assert isinstance(revenue_data, list)
    
    def test_get_top_selling_products(self, db_session: Session, sample_orders):
        """Test getting top selling products."""
        service = StatisticsService(db_session)
        top_products = service.get_top_selling_products(limit=10)
        
        assert isinstance(top_products, list)
        assert len(top_products) <= 10
    
    def test_get_total_sold_by_product(self, db_session: Session, sample_orders):
        """Test getting total sold quantity by product."""
        service = StatisticsService(db_session)
        sold_data = service.get_total_sold_by_product()
        
        assert isinstance(sold_data, list)
    
    def test_get_total_sold_all_products(self, db_session: Session, sample_orders):
        """Test getting total sold quantity for all products."""
        service = StatisticsService(db_session)
        total_sold = service.get_total_sold_all_products()
        
        assert isinstance(total_sold, int)
        assert total_sold >= 0
    
    def test_get_statistics_overview(self, db_session: Session, sample_orders):
        """Test getting statistics overview."""
        service = StatisticsService(db_session)
        overview = service.get_statistics_overview()
        
        assert "total_orders" in overview
        assert "total_revenue" in overview
        assert "orders_by_status" in overview
        assert "recent_orders" in overview

