"""
Tests for product upload API endpoints.
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
from src.database.models import Admin, AdminRole, Product, ProductVariation
from src.database.models.base import Base
from src.database.models.enums import DeliveryType
import contextlib

# Create test database file
test_db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
test_db_path = test_db_file.name
test_db_file.close()

def cleanup_test_db():
    """Clean up test database file."""
    with contextlib.suppress(Exception):
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)

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
def sample_product(test_db: Session):
    """Create sample product and variation."""
    product = Product(
        id="prod_1",
        name="Test Product",
        description="Test Description",
        delivery_type=DeliveryType.PRE_UPLOADED,
        is_active=True,
    )
    test_db.add(product)
    variation = ProductVariation(
        id="var_1",
        product_id="prod_1",
        name="Variation 1",
        price=100000,
        stock=10,
        is_active=True,
    )
    test_db.add(variation)
    test_db.commit()
    return product


def test_parse_text_content_requires_auth(client):
    """Test that parsing text content requires authentication."""
    response = client.post("/api/products/upload/parse", json={
        "content": "test",
        "format_type": "line_separated"
    })
    assert response.status_code == 401


def test_parse_text_content_line_separated(client, auth_token):
    """Test parsing line-separated content."""
    response = client.post(
        "/api/products/upload/parse",
        json={
            "content": "Product 1\nProduct 2\nProduct 3",
            "format_type": "line_separated"
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["parsed_data"]) == 3


def test_upload_products_requires_auth(client):
    """Test that uploading products requires authentication."""
    response = client.post("/api/products/upload", json={
        "products": []
    })
    assert response.status_code == 401


def test_upload_products(client, auth_token, sample_product):
    """Test uploading products."""
    response = client.post(
        "/api/products/upload",
        json={
            "products": [
                {
                    "product_id": "prod_1",
                    "variation_id": "var_1",
                    "product_data": "test data 1"
                },
                {
                    "product_id": "prod_1",
                    "variation_id": "var_1",
                    "product_data": "test data 2"
                },
            ]
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == 2
    assert data["failed"] == 0
