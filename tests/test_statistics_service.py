"""
Tests for statistics service.
"""
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from src.database.connection import create_engine_instance, get_session_factory, init_database
from src.database.models import Order, OrderItem, Product, ProductVariation, TopupOrder, AppSettings
from src.database.models.enums import OrderStatus, DeliveryType, TopupStatus
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


class TestStatisticsServiceNewBehaviors:
    """Tests for timezone fixes, updated_at revenue dating, and vendor revenue."""

    def _seed_app_settings(self, db_session: Session, tz: str = "Asia/Ho_Chi_Minh") -> None:
        """Seed AppSettings so _app_tz() returns a specific timezone."""
        db_session.add(AppSettings(id="global", timezone=tz))
        db_session.commit()

    def _make_order(
        self,
        db_session: Session,
        order_id: str,
        status: OrderStatus,
        amount: int,
        payment_provider: str | None,
        created_at: datetime,
        updated_at: datetime,
    ) -> Order:
        order = Order(
            id=order_id,
            user_id=100,
            status=status,
            total_amount=amount,
            payment_provider=payment_provider,
            created_at=created_at,
            updated_at=updated_at,
        )
        db_session.add(order)
        return order

    def _make_topup(
        self,
        db_session: Session,
        topup_id: str,
        amount: int,
        status: TopupStatus,
        updated_at: datetime,
    ) -> TopupOrder:
        topup = TopupOrder(
            id=topup_id,
            user_id=100,
            bot_user_id="botuser_1",
            amount=amount,
            status=status,
            updated_at=updated_at,
            created_at=updated_at,
        )
        db_session.add(topup)
        return topup

    def test_get_date_range_today_uses_app_tz(self, db_session: Session):
        """_get_date_range('today') window start should be local midnight converted to naive UTC."""
        from zoneinfo import ZoneInfo
        self._seed_app_settings(db_session, "Asia/Ho_Chi_Minh")
        service = StatisticsService(db_session)
        sd, ed = service._get_date_range("today")

        tz = ZoneInfo("Asia/Ho_Chi_Minh")
        now_local = datetime.now(tz=tz)
        expected_start_utc = now_local.replace(
            hour=0, minute=0, second=0, microsecond=0
        ).astimezone(timezone.utc).replace(tzinfo=None)

        # Allow 1-second tolerance for execution time
        diff = abs((sd - expected_start_utc).total_seconds())
        assert diff < 2, f"Expected ~{expected_start_utc}, got {sd}"
        assert sd.tzinfo is None, "Should be naive UTC"
        assert ed.tzinfo is None, "Should be naive UTC"

    def test_total_revenue_uses_updated_at(self, db_session: Session):
        """An order created yesterday but updated (paid) today counts in today's revenue."""
        self._seed_app_settings(db_session)
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        # created yesterday, paid (updated) today
        self._make_order(
            db_session, "order_upd_test", OrderStatus.PAID, 50000, "payos",
            created_at=yesterday, updated_at=now,
        )
        # created and updated yesterday → should NOT appear in today window
        self._make_order(
            db_session, "order_old", OrderStatus.PAID, 30000, "payos",
            created_at=yesterday, updated_at=yesterday,
        )
        db_session.commit()

        service = StatisticsService(db_session)
        today_revenue = service.get_total_revenue(period="today")
        # Only the order updated today should be in today's window
        assert today_revenue == 50000

    def test_total_revenue_all_time_no_filter(self, db_session: Session):
        """All-time revenue sums all PAID/DELIVERED orders regardless of date."""
        self._seed_app_settings(db_session)
        now = datetime.utcnow()
        self._make_order(db_session, "r1", OrderStatus.PAID, 10000, "payos", now, now)
        self._make_order(db_session, "r2", OrderStatus.DELIVERED, 20000, "balance", now, now)
        self._make_order(db_session, "r3", OrderStatus.PENDING, 5000, None, now, now)
        db_session.commit()

        service = StatisticsService(db_session)
        assert service.get_total_revenue() == 30000  # PAID + DELIVERED, not PENDING

    def test_get_vendor_revenue_excludes_balance_orders(self, db_session: Session):
        """Vendor revenue excludes orders paid via balance."""
        self._seed_app_settings(db_session)
        now = datetime.utcnow()
        self._make_order(db_session, "v_payos", OrderStatus.PAID, 100000, "payos", now, now)
        self._make_order(db_session, "v_pay2s", OrderStatus.DELIVERED, 80000, "pay2s", now, now)
        self._make_order(db_session, "v_balance", OrderStatus.PAID, 60000, "balance", now, now)
        self._make_order(db_session, "v_null", OrderStatus.PAID, 40000, None, now, now)
        db_session.commit()

        service = StatisticsService(db_session)
        vendor = service.get_vendor_revenue()
        # Only payos (100k) + pay2s (80k) = 180k; balance and null excluded
        assert vendor == 180000

    def test_get_vendor_revenue_includes_paid_topups(self, db_session: Session):
        """Vendor revenue includes PAID topups."""
        self._seed_app_settings(db_session)
        now = datetime.utcnow()
        self._make_topup(db_session, "TU_paid", 50000, TopupStatus.PAID, now)
        self._make_topup(db_session, "TU_pending", 30000, TopupStatus.PENDING, now)
        self._make_topup(db_session, "TU_cancelled", 20000, TopupStatus.CANCELLED, now)
        db_session.commit()

        service = StatisticsService(db_session)
        vendor = service.get_vendor_revenue()
        # Only PAID topup (50k) included
        assert vendor == 50000

    def test_get_vendor_revenue_combined(self, db_session: Session):
        """Vendor revenue = QR orders + PAID topups."""
        self._seed_app_settings(db_session)
        now = datetime.utcnow()
        self._make_order(db_session, "combo_qr", OrderStatus.PAID, 70000, "payos", now, now)
        self._make_order(db_session, "combo_bal", OrderStatus.PAID, 30000, "balance", now, now)
        self._make_topup(db_session, "combo_tu", 25000, TopupStatus.PAID, now)
        db_session.commit()

        service = StatisticsService(db_session)
        vendor = service.get_vendor_revenue()
        assert vendor == 95000  # 70k QR + 25k topup

    def test_get_vendor_revenue_windowed_today(self, db_session: Session):
        """Vendor revenue period filter windows on updated_at."""
        self._seed_app_settings(db_session)
        now = datetime.utcnow()
        yesterday = now - timedelta(days=2)

        self._make_order(db_session, "vr_today", OrderStatus.PAID, 50000, "payos",
                         created_at=yesterday, updated_at=now)
        self._make_order(db_session, "vr_old", OrderStatus.PAID, 40000, "payos",
                         created_at=yesterday, updated_at=yesterday)
        db_session.commit()

        service = StatisticsService(db_session)
        vendor_today = service.get_vendor_revenue(period="today")
        assert vendor_today == 50000

    def test_overview_includes_vendor_revenue_keys(self, db_session: Session):
        """Statistics overview includes vendor_revenue and vendor_revenue_today."""
        self._seed_app_settings(db_session)
        service = StatisticsService(db_session)
        overview = service.get_statistics_overview()

        assert "vendor_revenue" in overview
        assert "vendor_revenue_today" in overview
        assert isinstance(overview["vendor_revenue"], int)
        assert isinstance(overview["vendor_revenue_today"], int)

