"""
Tests for orders API endpoints.
Following TDD: Write tests first, then implement endpoints.
"""
import atexit
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.dashboard.auth import create_access_token, get_db, get_password_hash
from src.dashboard.main import app

# Import all models to ensure they're registered
from src.database.models import *
from src.database.models import (
    Admin,
    AdminRole,
    Order,
    OrderItem,
    Product,
    ProductVariation,
)
from src.database.models.base import Base
from src.database.models.enums import DeliveryType, OrderStatus

# Create test database file
test_db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
test_db_path = test_db_file.name
test_db_file.close()

def cleanup_test_db():
    """Clean up test database file."""
    try:
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)
    except Exception:
        pass

atexit.register(cleanup_test_db)

test_engine = create_engine(
    f"sqlite:///{test_db_path}",
    echo=False,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)
Base.metadata.create_all(test_engine)
TestSession = sessionmaker(bind=test_engine)


def override_get_db():
    """Override get_db dependency for testing."""
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    """Create test client with database override."""
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True, scope="function")
def setup_database():
    """Set up test database before each test."""
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield
    # Clean up after test
    with test_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.commit()


@pytest.fixture
def test_db():
    """Create test database session."""
    session = TestSession()
    yield session
    session.close()


@pytest.fixture
def test_admin(test_db: Session):
    """Create test admin user."""
    admin = Admin(
        id="admin_1",
        username="testadmin",
        email="test@example.com",
        password_hash=get_password_hash("testpass123"),
        full_name="Test Admin",
        role=AdminRole.ADMIN,
        is_active=True,
    )
    test_db.add(admin)
    test_db.commit()
    return admin


@pytest.fixture
def auth_token(test_admin: Admin):
    """Create auth token for test admin."""
    return create_access_token(data={"sub": test_admin.username})


@pytest.fixture
def sample_data(test_db: Session):
    """Create sample products, variations, and orders."""
    # Create product
    product = Product(
        id="prod_1",
        name="Test Product",
        description="Test",
        delivery_type=DeliveryType.PRE_UPLOADED,
        is_active=True,
    )
    test_db.add(product)
    
    # Create variation
    variation = ProductVariation(
        id="var_1",
        product_id="prod_1",
        name="Variation 1",
        price=100000,
        stock=10,
        is_active=True,
    )
    test_db.add(variation)
    
    # Create orders
    order1 = Order(
        id="order_1",
        user_id=123456789,
        status=OrderStatus.PENDING,
        total_amount=100000,
    )
    test_db.add(order1)
    
    order2 = Order(
        id="order_2",
        user_id=123456789,
        status=OrderStatus.PAID,
        total_amount=200000,
        payment_transaction_id="txn_123",
    )
    test_db.add(order2)
    
    order3 = Order(
        id="order_3",
        user_id=987654321,
        status=OrderStatus.DELIVERED,
        total_amount=150000,
        payment_transaction_id="txn_456",
    )
    test_db.add(order3)
    
    # Create order items
    item1 = OrderItem(
        id="item_1",
        order_id="order_1",
        product_id="prod_1",
        variation_id="var_1",
        quantity=1,
        unit_price=100000,
        subtotal=100000,
    )
    test_db.add(item1)
    
    item2 = OrderItem(
        id="item_2",
        order_id="order_2",
        product_id="prod_1",
        variation_id="var_1",
        quantity=2,
        unit_price=100000,
        subtotal=200000,
    )
    test_db.add(item2)
    
    test_db.commit()
    return {
        "product": product,
        "variation": variation,
        "order1": order1,
        "order2": order2,
        "order3": order3,
    }


def test_list_orders_requires_auth(client):
    """Test that listing orders requires authentication."""
    response = client.get("/api/orders")
    assert response.status_code == 401


def test_list_orders_success(client, auth_token, sample_data):
    """Test listing orders successfully."""
    response = client.get(
        "/api/orders",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "per_page" in data
    assert "total_pages" in data
    assert len(data["items"]) > 0


def test_list_orders_with_pagination(client, auth_token, sample_data):
    """Test listing orders with pagination."""
    response = client.get(
        "/api/orders?page=1&per_page=2",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 2
    assert data["page"] == 1
    assert data["per_page"] == 2


def test_list_orders_filter_by_status(client, auth_token, sample_data):
    """Test filtering orders by status."""
    response = client.get(
        "/api/orders?status=pending",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert all(item["status"] == "pending" for item in data["items"])


def test_list_orders_filter_by_user_id(client, auth_token, sample_data):
    """Test filtering orders by user ID."""
    response = client.get(
        "/api/orders?user_id=123456789",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert all(item["user_id"] == 123456789 for item in data["items"])


def test_list_orders_filter_by_product_id(client, auth_token, sample_data):
    """Test filtering orders by product ID."""
    response = client.get(
        "/api/orders?product_id=prod_1",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    # All orders should contain the product
    assert len(data["items"]) > 0


def test_list_orders_search(client, auth_token, sample_data):
    """Test searching orders by order ID."""
    response = client.get(
        "/api/orders?search=order_1",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) > 0
    assert any(item["id"] == "order_1" for item in data["items"])


def test_list_orders_sort_by_created_at(client, auth_token, sample_data):
    """Test sorting orders by created_at."""
    response = client.get(
        "/api/orders?sort_by=created_at&sort_order=desc",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    if len(data["items"]) > 1:
        # Check that orders are sorted descending
        dates = [item["created_at"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)


def test_get_order_requires_auth(client):
    """Test that getting order details requires authentication."""
    response = client.get("/api/orders/order_1")
    assert response.status_code == 401


def test_get_order_success(client, auth_token, sample_data):
    """Test getting order details successfully."""
    response = client.get(
        "/api/orders/order_1",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "order_1"
    assert "items" in data
    assert len(data["items"]) > 0


def test_get_order_not_found(client, auth_token):
    """Test getting non-existent order."""
    response = client.get(
        "/api/orders/nonexistent",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 404


def test_update_order_status_requires_auth(client):
    """Test that updating order status requires authentication."""
    response = client.put("/api/orders/order_1/status", json={"status": "paid"})
    assert response.status_code == 401


def test_update_order_status_success(client, auth_token, sample_data):
    """Test updating order status successfully."""
    response = client.put(
        "/api/orders/order_1/status",
        json={"status": "paid"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "paid"


def test_update_order_status_invalid_status(client, auth_token, sample_data):
    """Test updating order status with invalid status."""
    response = client.put(
        "/api/orders/order_1/status",
        json={"status": "invalid_status"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 400


def test_update_order_status_not_found(client, auth_token):
    """Test updating status of non-existent order."""
    response = client.put(
        "/api/orders/nonexistent/status",
        json={"status": "paid"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 404


def test_export_orders_requires_auth(client):
    """Test that exporting orders requires authentication."""
    response = client.get("/api/orders/export")
    assert response.status_code == 401


def test_export_orders_success(client, auth_token, sample_data):
    """Test exporting orders successfully."""
    response = client.get(
        "/api/orders/export",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment" in response.headers["content-disposition"]


def test_export_orders_with_filters(client, auth_token, sample_data):
    """Test exporting orders with filters."""
    response = client.get(
        "/api/orders/export?status=pending",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"

