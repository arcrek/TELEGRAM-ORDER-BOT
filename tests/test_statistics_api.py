"""
Tests for statistics API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.dashboard.main import app
from src.database.models import Admin, AdminRole
from src.database.models.base import Base
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
    # Clean up all data first
    with test_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            try:
                conn.execute(table.delete())
            except Exception:
                pass
        conn.commit()
    
    # Recreate tables
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    
    # Create admin user in the test database
    session = TestSession()
    try:
        admin = Admin(
            id="admin_1",
            username="testadmin",
            email="test@example.com",
            password_hash=get_password_hash("testpass123"),
            full_name="Test Admin",
            role=AdminRole.ADMIN,
            is_active=True,
        )
        session.add(admin)
        session.commit()
    finally:
        session.close()
    
    yield


@pytest.fixture
def test_db():
    """Create test database session."""
    session = TestSession()
    yield session
    session.close()


@pytest.fixture
def test_admin(test_db: Session):
    """Get test admin user."""
    admin = test_db.query(Admin).filter_by(email="test@example.com").first()
    if not admin:
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
        test_db.refresh(admin)
    return admin


@pytest.fixture
def auth_token(test_admin: Admin):
    """Create auth token for test admin."""
    return create_access_token(data={"sub": test_admin.username})


def test_get_statistics_overview_requires_auth(client):
    """Test that statistics overview requires authentication."""
    response = client.get("/api/statistics/overview")
    assert response.status_code == 401


def test_get_statistics_overview(client, auth_token):
    """Test getting statistics overview."""
    response = client.get(
        "/api/statistics/overview",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_orders" in data
    assert "total_revenue" in data
    assert "orders_by_status" in data


def test_get_orders_count(client, auth_token):
    """Test getting orders count."""
    response = client.get(
        "/api/statistics/orders/count",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert isinstance(data["count"], int)


def test_get_orders_count_with_period(client, auth_token):
    """Test getting orders count with period filter."""
    response = client.get(
        "/api/statistics/orders/count?period=today",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert data["period"] == "today"


def test_get_revenue(client, auth_token):
    """Test getting revenue."""
    response = client.get(
        "/api/statistics/revenue",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "revenue" in data
    assert isinstance(data["revenue"], int)


def test_get_orders_by_status(client, auth_token):
    """Test getting orders by status."""
    response = client.get(
        "/api/statistics/orders/by-status",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


def test_get_orders_by_product(client, auth_token):
    """Test getting orders by product."""
    response = client.get(
        "/api/statistics/orders/by-product",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_revenue_over_time(client, auth_token):
    """Test getting revenue over time."""
    response = client.get(
        "/api/statistics/revenue/over-time?interval=daily&days=30",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_top_selling_products(client, auth_token):
    """Test getting top selling products."""
    response = client.get(
        "/api/statistics/products/top-selling?limit=10",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_total_sold_by_product(client, auth_token):
    """Test getting total sold by product."""
    response = client.get(
        "/api/statistics/products/sold",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_total_sold_all_products(client, auth_token):
    """Test getting total sold for all products."""
    response = client.get(
        "/api/statistics/products/total-sold",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_sold" in data
    assert isinstance(data["total_sold"], int)


def test_get_statistics_overview_includes_vendor_revenue(client, auth_token):
    """Test that the overview endpoint includes vendor_revenue keys."""
    response = client.get(
        "/api/statistics/overview",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "vendor_revenue" in data
    assert "vendor_revenue_today" in data
    assert isinstance(data["vendor_revenue"], int)
    assert isinstance(data["vendor_revenue_today"], int)


def test_get_statistics_overview_all_time(client, auth_token):
    """No range params → all-time (returns all data)."""
    response = client.get(
        "/api/statistics/overview",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_revenue" in data


def test_get_statistics_overview_custom_range(client, auth_token):
    """Custom range sends from/to ISO datetimes."""
    import datetime as dt
    now = dt.datetime.utcnow()
    from_iso = (now - dt.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    to_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    response = client.get(
        f"/api/statistics/overview?range=custom&from={from_iso}&to={to_iso}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_revenue" in data


def test_get_statistics_overview_all_preset(client, auth_token):
    """'all' range preset → all-time (same as no params)."""
    response = client.get(
        "/api/statistics/overview?range=all",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_revenue" in data

