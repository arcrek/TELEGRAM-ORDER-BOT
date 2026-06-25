"""
Tests for suppliers API endpoints.
Following TDD: Write tests first, then implement endpoints.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Supplier module disabled in dashboard API")
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.dashboard.main import app
from src.database.models import Admin, AdminRole, Supplier, SupplierOrder, Order, Product
from src.database.models.base import Base
from src.database.models.enums import SupplierOrderStatus, OrderStatus, DeliveryType
from src.dashboard.auth import get_password_hash, create_access_token, get_db

# Import all models to ensure they're registered
from src.database.models import *  # noqa: F401, F403

import tempfile
import os
import atexit

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
def sample_suppliers(test_db: Session):
    """Create sample suppliers."""
    supplier1 = Supplier(
        id="supp_1",
        telegram_user_id=123456789,
        name="Supplier 1",
        is_active=True,
    )
    supplier2 = Supplier(
        id="supp_2",
        telegram_user_id=987654321,
        name="Supplier 2",
        is_active=False,
    )
    test_db.add(supplier1)
    test_db.add(supplier2)
    test_db.commit()
    return [supplier1, supplier2]


@pytest.fixture
def sample_orders_with_supplier_orders(test_db: Session, sample_suppliers):
    """Create sample orders with supplier orders."""
    # Create a product
    product = Product(
        id="prod_1",
        name="Test Product",
        description="Test",
        delivery_type=DeliveryType.SUPPLIER_BASED,
        is_active=True,
    )
    test_db.add(product)
    test_db.commit()
    
    # Create orders
    order1 = Order(
        id="order_1",
        user_id=111111111,
        status=OrderStatus.PAID,
        total_amount=100000,
    )
    order2 = Order(
        id="order_2",
        user_id=222222222,
        status=OrderStatus.DELIVERED,
        total_amount=200000,
    )
    test_db.add(order1)
    test_db.add(order2)
    test_db.commit()
    
    # Create supplier orders
    supplier_order1 = SupplierOrder(
        id="so_1",
        order_id="order_1",
        supplier_id="supp_1",
        status=SupplierOrderStatus.PENDING,
    )
    supplier_order2 = SupplierOrder(
        id="so_2",
        order_id="order_2",
        supplier_id="supp_1",
        status=SupplierOrderStatus.DELIVERED,
    )
    test_db.add(supplier_order1)
    test_db.add(supplier_order2)
    test_db.commit()
    
    return [order1, order2]


def test_list_suppliers_requires_auth(client):
    """Test that listing suppliers requires authentication."""
    response = client.get("/api/suppliers")
    assert response.status_code == 401


def test_list_suppliers_all(client, auth_token, sample_suppliers):
    """Test listing all suppliers."""
    response = client.get(
        "/api/suppliers",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 2


def test_list_suppliers_only_active(client, auth_token, sample_suppliers):
    """Test listing only active suppliers."""
    response = client.get(
        "/api/suppliers?only_active=true",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["is_active"] is True


def test_get_supplier_requires_auth(client):
    """Test that getting a supplier requires authentication."""
    response = client.get("/api/suppliers/supp_1")
    assert response.status_code == 401


def test_get_supplier_success(client, auth_token, sample_suppliers):
    """Test getting a supplier by ID."""
    response = client.get(
        "/api/suppliers/supp_1",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "supp_1"
    assert data["name"] == "Supplier 1"
    assert data["telegram_user_id"] == 123456789
    assert data["is_active"] is True


def test_get_supplier_not_found(client, auth_token):
    """Test getting a non-existent supplier."""
    response = client.get(
        "/api/suppliers/nonexistent",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 404


def test_update_supplier_status_requires_auth(client):
    """Test that updating supplier status requires authentication."""
    response = client.put("/api/suppliers/supp_1/status", json={"is_active": False})
    assert response.status_code == 401


def test_update_supplier_status_success(client, auth_token, sample_suppliers):
    """Test updating supplier status."""
    response = client.put(
        "/api/suppliers/supp_1/status",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_active"] is False
    
    # Verify it's updated
    get_response = client.get(
        "/api/suppliers/supp_1",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert get_response.json()["is_active"] is False


def test_update_supplier_status_not_found(client, auth_token):
    """Test updating status for non-existent supplier."""
    response = client.put(
        "/api/suppliers/nonexistent/status",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 404


def test_get_supplier_order_history_requires_auth(client):
    """Test that getting supplier order history requires authentication."""
    response = client.get("/api/suppliers/supp_1/orders")
    assert response.status_code == 401


def test_get_supplier_order_history_success(client, auth_token, sample_suppliers, sample_orders_with_supplier_orders):
    """Test getting supplier order history."""
    response = client.get(
        "/api/suppliers/supp_1/orders",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 2
    assert "supplier_order_id" in data["items"][0]
    assert "order_id" in data["items"][0]
    assert "status" in data["items"][0]


def test_get_supplier_order_history_not_found(client, auth_token):
    """Test getting order history for non-existent supplier."""
    response = client.get(
        "/api/suppliers/nonexistent/orders",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 404


def test_get_supplier_statistics_requires_auth(client):
    """Test that getting supplier statistics requires authentication."""
    response = client.get("/api/suppliers/supp_1/statistics")
    assert response.status_code == 401


def test_get_supplier_statistics_success(client, auth_token, sample_suppliers, sample_orders_with_supplier_orders):
    """Test getting supplier statistics."""
    response = client.get(
        "/api/suppliers/supp_1/statistics",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "supplier_id" in data
    assert "supplier_name" in data
    assert "total_orders" in data
    assert "pending_orders" in data
    assert "delivered_orders" in data
    assert "total_revenue" in data
    assert data["total_orders"] == 2
    assert data["delivered_orders"] == 1
    assert data["total_revenue"] == 200000  # Only delivered orders count


def test_get_supplier_statistics_not_found(client, auth_token):
    """Test getting statistics for non-existent supplier."""
    response = client.get(
        "/api/suppliers/nonexistent/statistics",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 404

