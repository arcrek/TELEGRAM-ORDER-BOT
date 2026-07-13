"""
Tests for product supplier assignment API endpoints.
Following TDD: Write tests first, then implement endpoints.
"""
# ruff: noqa: E402
import pytest

pytestmark = pytest.mark.skip(reason="Supplier module disabled in dashboard API")
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.dashboard.main import app
from src.database.models import Admin, AdminRole, Product, Supplier
from src.database.models.base import Base
from src.database.models.enums import DeliveryType
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
def sample_data(test_db: Session):
    """Create sample products and suppliers."""
    product = Product(
        id="prod_1",
        name="Test Product",
        description="Test",
        delivery_type=DeliveryType.SUPPLIER_BASED,
        is_active=True,
    )
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
        is_active=True,
    )
    test_db.add(product)
    test_db.add(supplier1)
    test_db.add(supplier2)
    test_db.commit()
    return {"product": product, "supplier1": supplier1, "supplier2": supplier2}


def test_create_assignment_requires_auth(client):
    """Test that creating assignment requires authentication."""
    response = client.post("/api/suppliers/assignments", json={
        "product_id": "prod_1",
        "supplier_id": "supp_1",
        "is_primary": False,
    })
    assert response.status_code == 401


def test_create_assignment_success(client, auth_token, sample_data):
    """Test creating an assignment."""
    response = client.post(
        "/api/suppliers/assignments",
        json={
            "product_id": "prod_1",
            "supplier_id": "supp_1",
            "is_primary": False,
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["product_id"] == "prod_1"
    assert data["supplier_id"] == "supp_1"
    assert data["is_primary"] is False


def test_create_assignment_primary(client, auth_token, sample_data):
    """Test creating a primary assignment."""
    response = client.post(
        "/api/suppliers/assignments",
        json={
            "product_id": "prod_1",
            "supplier_id": "supp_1",
            "is_primary": True,
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["is_primary"] is True


def test_create_assignment_duplicate(client, auth_token, sample_data):
    """Test creating duplicate assignment fails."""
    # Create first assignment
    client.post(
        "/api/suppliers/assignments",
        json={
            "product_id": "prod_1",
            "supplier_id": "supp_1",
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    # Try to create duplicate
    response = client.post(
        "/api/suppliers/assignments",
        json={
            "product_id": "prod_1",
            "supplier_id": "supp_1",
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 400


def test_get_assignments_by_product_requires_auth(client):
    """Test that getting assignments by product requires authentication."""
    response = client.get("/api/products/prod_1/suppliers")
    assert response.status_code == 401


def test_get_assignments_by_product_success(client, auth_token, sample_data):
    """Test getting assignments by product."""
    # Create assignments
    client.post(
        "/api/suppliers/assignments",
        json={"product_id": "prod_1", "supplier_id": "supp_1", "is_primary": True},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    client.post(
        "/api/suppliers/assignments",
        json={"product_id": "prod_1", "supplier_id": "supp_2", "is_primary": False},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    response = client.get(
        "/api/products/prod_1/suppliers",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 2
    # Primary should be first
    assert data["items"][0]["is_primary"] is True


def test_get_assignments_by_supplier_requires_auth(client):
    """Test that getting assignments by supplier requires authentication."""
    response = client.get("/api/suppliers/supp_1/products")
    assert response.status_code == 401


def test_get_assignments_by_supplier_success(client, auth_token, sample_data, test_db):
    """Test getting assignments by supplier."""
    # Create another product
    product2 = Product(
        id="prod_2",
        name="Product 2",
        description="Test",
        delivery_type=DeliveryType.SUPPLIER_BASED,
        is_active=True,
    )
    test_db.add(product2)
    test_db.commit()
    
    # Create assignments
    client.post(
        "/api/suppliers/assignments",
        json={"product_id": "prod_1", "supplier_id": "supp_1"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    client.post(
        "/api/suppliers/assignments",
        json={"product_id": "prod_2", "supplier_id": "supp_1"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    response = client.get(
        "/api/suppliers/supp_1/products",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 2


def test_update_assignment_requires_auth(client):
    """Test that updating assignment requires authentication."""
    response = client.put("/api/suppliers/assignments", json={
        "product_id": "prod_1",
        "supplier_id": "supp_1",
        "is_primary": True,
    })
    assert response.status_code == 401


def test_update_assignment_success(client, auth_token, sample_data):
    """Test updating an assignment."""
    # Create assignment
    client.post(
        "/api/suppliers/assignments",
        json={"product_id": "prod_1", "supplier_id": "supp_1", "is_primary": False},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    # Update to primary
    response = client.put(
        "/api/suppliers/assignments",
        json={
            "product_id": "prod_1",
            "supplier_id": "supp_1",
            "is_primary": True,
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_primary"] is True


def test_delete_assignment_requires_auth(client):
    """Test that deleting assignment requires authentication."""
    response = client.delete("/api/suppliers/assignments?product_id=prod_1&supplier_id=supp_1")
    assert response.status_code == 401


def test_delete_assignment_success(client, auth_token, sample_data):
    """Test deleting an assignment."""
    # Create assignment
    client.post(
        "/api/suppliers/assignments",
        json={"product_id": "prod_1", "supplier_id": "supp_1"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    # Delete assignment
    response = client.delete(
        "/api/suppliers/assignments?product_id=prod_1&supplier_id=supp_1",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    
    # Verify it's deleted
    get_response = client.get(
        "/api/products/prod_1/suppliers",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert len(get_response.json()["items"]) == 0


def test_delete_assignment_not_found(client, auth_token):
    """Test deleting non-existent assignment."""
    response = client.delete(
        "/api/suppliers/assignments?product_id=nonexistent&supplier_id=nonexistent",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 404
