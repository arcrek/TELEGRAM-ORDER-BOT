"""
Tests for products API endpoints.
Following TDD: Write tests first, then implement endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.dashboard.main import app
from src.database.models import Admin, AdminRole, Product
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
    yield


@pytest.fixture
def test_db():
    """Create test database session."""
    session = TestSession()
    yield session
    session.close()


@pytest.fixture
def test_admin(test_db: Session):
    """Create test admin user."""
    # Check if admin already exists
    existing = test_db.query(Admin).filter_by(email="test@example.com").first()
    if existing:
        return existing
    
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


@pytest.fixture
def sample_products(test_db: Session):
    """Create sample products for testing."""
    products = []
    for i in range(5):
        product = Product(
            id=f"prod_{i}",
            name=f"Product {i}",
            description=f"Description {i}",
            delivery_type=DeliveryType.PRE_UPLOADED if i % 2 == 0 else DeliveryType.SUPPLIER_BASED,
            is_active=True,
        )
        test_db.add(product)
        products.append(product)
    
    test_db.commit()
    return products


class TestProductsAPI:
    """Test products API endpoints."""
    
    def test_list_products_requires_auth(self, client):
        """Test that listing products requires authentication."""
        response = client.get("/api/products/")
        assert response.status_code == 401
    
    def test_list_products(self, client, auth_token, sample_products):
        """Test listing products."""
        response = client.get(
            "/api/products/",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert len(data["items"]) > 0
    
    def test_list_products_with_pagination(self, client, auth_token, sample_products):
        """Test listing products with pagination."""
        response = client.get(
            "/api/products/?page=1&per_page=2",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 2
        assert data["page"] == 1
        assert data["per_page"] == 2
    
    def test_list_products_with_search(self, client, auth_token, sample_products):
        """Test listing products with search."""
        response = client.get(
            "/api/products/?search=Product 0",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 1
        assert "Product 0" in data["items"][0]["name"]
    
    def test_list_products_with_filter_active(self, client, auth_token, sample_products):
        """Test listing products with active filter."""
        response = client.get(
            "/api/products/?only_active=true",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert all(item["is_active"] for item in data["items"])
    
    def test_list_products_with_sort(self, client, auth_token, sample_products):
        """Test listing products with sorting."""
        response = client.get(
            "/api/products/?sort_by=name&sort_order=desc",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        names = [item["name"] for item in data["items"]]
        assert names == sorted(names, reverse=True)
    
    def test_get_product_by_id_requires_auth(self, client):
        """Test that getting product requires authentication."""
        response = client.get("/api/products/prod_1")
        assert response.status_code == 401
    
    def test_get_product_by_id(self, client, auth_token, sample_products):
        """Test getting product by ID."""
        response = client.get(
            "/api/products/prod_0",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "prod_0"
        assert data["name"] == "Product 0"
    
    def test_get_product_not_found(self, client, auth_token):
        """Test getting non-existent product."""
        response = client.get(
            "/api/products/nonexistent",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 404
    
    def test_create_product_requires_auth(self, client):
        """Test that creating product requires authentication."""
        response = client.post("/api/products/", json={
            "id": "new_prod",
            "name": "New Product",
            "description": "Description",
            "delivery_type": "pre_uploaded",
        })
        assert response.status_code == 401
    
    def test_create_product(self, client, auth_token, test_db):
        """Test creating a new product."""
        response = client.post(
            "/api/products/",
            json={
                "id": "new_prod",
                "name": "New Product",
                "description": "New Description",
                "delivery_type": "pre_uploaded",
                "is_active": True,
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "new_prod"
        assert data["name"] == "New Product"
        assert data["delivery_type"] == "pre_uploaded"
        
        # Verify it was created in database
        from src.database.services.product_service import ProductService
        service = ProductService(test_db)
        product = service.get_product_by_id("new_prod")
        assert product is not None
        assert product.name == "New Product"
    
    def test_create_product_duplicate_id(self, client, auth_token, sample_products):
        """Test creating product with duplicate ID."""
        response = client.post(
            "/api/products/",
            json={
                "id": "prod_0",
                "name": "Duplicate",
                "delivery_type": "pre_uploaded",
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 400
    
    def test_update_product_requires_auth(self, client):
        """Test that updating product requires authentication."""
        response = client.put("/api/products/prod_0", json={"name": "Updated"})
        assert response.status_code == 401
    
    def test_update_product(self, client, auth_token, sample_products):
        """Test updating a product."""
        response = client.put(
            "/api/products/prod_0",
            json={
                "name": "Updated Product",
                "description": "Updated Description",
                "delivery_type": "supplier_based",
                "is_active": False,
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Product"
        assert data["description"] == "Updated Description"
        assert data["delivery_type"] == "supplier_based"
        assert data["is_active"] is False
    
    def test_update_product_not_found(self, client, auth_token):
        """Test updating non-existent product."""
        response = client.put(
            "/api/products/nonexistent",
            json={"name": "Updated"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 404
    
    def test_delete_product_requires_auth(self, client):
        """Test that deleting product requires authentication."""
        response = client.delete("/api/products/prod_0")
        assert response.status_code == 401
    
    def test_delete_product(self, client, auth_token, sample_products, test_db):
        """Test deleting a product (hard delete)."""
        response = client.delete(
            "/api/products/prod_0",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        # Verify it was hard deleted
        from src.database.services.product_service import ProductService
        service = ProductService(test_db)
        product = service.get_product_by_id("prod_0")
        assert product is None
    
    def test_delete_product_not_found(self, client, auth_token):
        """Test deleting non-existent product."""
        response = client.delete(
            "/api/products/nonexistent",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 404
