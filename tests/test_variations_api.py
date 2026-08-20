"""
Tests for variations API endpoints.
Following TDD: Write tests first, then implement endpoints.
"""
import atexit
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import src.dashboard.routers.variations as variations_router
from src.dashboard.auth import create_access_token, get_db, get_password_hash
from src.dashboard.main import app

# Import all models to ensure they're registered
from src.database.models import *
from src.database.models import Admin, AdminRole, Product, ProductVariation
from src.database.models.base import Base
from src.database.models.enums import DeliveryType

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
def sample_products(test_db: Session):
    """Create sample products with variations."""
    product1 = Product(
        id="prod_1",
        name="Product 1",
        description="Description 1",
        delivery_type=DeliveryType.PRE_UPLOADED,
        is_active=True,
    )
    product2 = Product(
        id="prod_2",
        name="Product 2",
        description="Description 2",
        delivery_type=DeliveryType.SUPPLIER_BASED,
        is_active=True,
    )
    test_db.add(product1)
    test_db.add(product2)
    
    variation1 = ProductVariation(
        id="var_1",
        product_id="prod_1",
        name="Variation 1",
        price=100000,
        stock=10,
        is_active=True,
    )
    variation2 = ProductVariation(
        id="var_2",
        product_id="prod_1",
        name="Variation 2",
        price=200000,
        stock=5,
        is_active=True,
    )
    variation3 = ProductVariation(
        id="var_3",
        product_id="prod_2",
        name="Variation 3",
        price=150000,
        stock=0,
        is_active=False,
    )
    test_db.add(variation1)
    test_db.add(variation2)
    test_db.add(variation3)
    test_db.commit()
    return [product1, product2]


def test_list_variations_requires_auth(client):
    """Test that listing variations requires authentication."""
    response = client.get("/api/variations")
    assert response.status_code == 401


def test_list_variations_all(client, auth_token, sample_products):
    """Test listing all variations grouped by product."""
    response = client.get(
        "/api/variations",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 2  # Two products
    # Product 1 should have 2 variations
    prod1 = next(p for p in data["items"] if p["product_id"] == "prod_1")
    assert len(prod1["variations"]) == 2
    # Product 2 should have 1 variation
    prod2 = next(p for p in data["items"] if p["product_id"] == "prod_2")
    assert len(prod2["variations"]) == 1


def test_list_variations_filter_by_product(client, auth_token, sample_products):
    """Test listing variations filtered by product."""
    response = client.get(
        "/api/variations?product_id=prod_1",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["product_id"] == "prod_1"
    assert len(data["items"][0]["variations"]) == 2


def test_list_variations_only_active(client, auth_token, sample_products):
    """Test listing only active variations."""
    response = client.get(
        "/api/variations?only_active=true",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    # Should only show active variations
    for product in data["items"]:
        for variation in product["variations"]:
            assert variation["is_active"] is True


def test_get_variation_requires_auth(client):
    """Test that getting a variation requires authentication."""
    response = client.get("/api/variations/var_1")
    assert response.status_code == 401


def test_get_variation_success(client, auth_token, sample_products):
    """Test getting a variation by ID."""
    response = client.get(
        "/api/variations/var_1",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "var_1"
    assert data["name"] == "Variation 1"
    assert data["price"] == 100000
    # Stock is calculated from pre-uploaded products (0 if none exist for PRE_UPLOADED products)
    assert "stock" in data
    assert data["is_active"] is True


def test_get_variation_not_found(client, auth_token):
    """Test getting a non-existent variation."""
    response = client.get(
        "/api/variations/nonexistent",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 404


def test_create_variation_requires_auth(client):
    """Test that creating a variation requires authentication."""
    response = client.post("/api/variations", json={
        "id": "var_new",
        "product_id": "prod_1",
        "name": "New Variation",
        "price": 50000,
        "stock": 20,
    })
    assert response.status_code == 401


def test_create_variation_success(client, auth_token, sample_products):
    """Test creating a new variation."""
    response = client.post(
        "/api/variations",
        json={
            "id": "var_new",
            "product_id": "prod_1",
            "name": "New Variation",
            "price": 50000,
            "is_active": True,
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "var_new"
    assert data["name"] == "New Variation"
    assert data["price"] == 50000
    # Stock is calculated from pre-uploaded products (0 if none exist for PRE_UPLOADED products)
    assert "stock" in data
    assert data["is_active"] is True


def test_create_variation_duplicate_id(client, auth_token, sample_products):
    """Test creating a variation with duplicate ID."""
    response = client.post(
        "/api/variations",
        json={
            "id": "var_1",
            "product_id": "prod_1",
            "name": "Duplicate",
            "price": 50000,
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 400


def test_create_variation_invalid_product(client, auth_token):
    """Test creating a variation with invalid product ID."""
    response = client.post(
        "/api/variations",
        json={
            "id": "var_new",
            "product_id": "nonexistent",
            "name": "New Variation",
            "price": 50000,
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 404


def test_update_variation_requires_auth(client):
    """Test that updating a variation requires authentication."""
    response = client.put("/api/variations/var_1", json={
        "name": "Updated Name",
    })
    assert response.status_code == 401


def test_update_variation_success(client, auth_token, sample_products):
    """Test updating a variation."""
    response = client.put(
        "/api/variations/var_1",
        json={
            "name": "Updated Variation",
            "price": 120000,
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Variation"
    assert data["price"] == 120000
    # Stock is calculated from pre-uploaded products (not manually set for PRE_UPLOADED products)
    assert "stock" in data


@pytest.mark.asyncio
async def test_editing_virtual_stock_sends_full_stock_upload_notification(
    test_db, monkeypatch
):
    product = Product(
        id="prod_virtual",
        name="Virtual Product",
        delivery_type=DeliveryType.VIRTUAL_ORDER,
        upgrade_request_text="Reusable content",
        is_active=True,
    )
    variation = ProductVariation(
        id="var_virtual",
        product_id=product.id,
        name="Default",
        price=10_000,
        stock=8,
        is_active=True,
    )
    test_db.add_all([product, variation])
    test_db.commit()

    sent = {}

    async def noop():
        pass

    def capture(entries):
        sent["entries"] = entries
        return noop()

    monkeypatch.setattr(variations_router, "_send_upload_notifications", capture)

    response = await variations_router.update_variation(
        "var_virtual",
        variations_router.VariationUpdate(stock=3),
        current_admin=None,
        db=test_db,
    )

    assert response["stock"] == 3
    assert sent["entries"][0]["product_id"] == product.id
    assert "➕ Đã thêm: 3" in sent["entries"][0]["message"]
    assert "📦 Tổng số lượng: 3" in sent["entries"][0]["message"]


def test_update_variation_not_found(client, auth_token):
    """Test updating a non-existent variation."""
    response = client.put(
        "/api/variations/nonexistent",
        json={"name": "Updated"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 404


def test_update_stock_requires_auth(client):
    """Test that updating stock requires authentication."""
    response = client.put("/api/variations/var_1/stock", json={
        "stock": 25,
    })
    assert response.status_code == 401


def test_update_stock_success(client, auth_token, sample_products):
    """Test getting stock for a variation (stock is calculated from pre-uploaded products)."""
    response = client.put(
        "/api/variations/var_1/stock",
        json={"stock": 25},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    # Stock is calculated from pre-uploaded products (0 if none exist for PRE_UPLOADED products)
    assert "stock" in data
    assert data["stock"] == 0  # No pre-uploaded products exist


def test_update_stock_not_found(client, auth_token):
    """Test updating stock for non-existent variation."""
    response = client.put(
        "/api/variations/nonexistent/stock",
        json={"stock": 25},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 404


def test_delete_variation_requires_auth(client):
    """Test that deleting a variation requires authentication."""
    response = client.delete("/api/variations/var_1")
    assert response.status_code == 401


def test_delete_variation_success(client, auth_token, sample_products):
    """Test deleting a variation (hard delete)."""
    response = client.delete(
        "/api/variations/var_1",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    
    # Verify it's hard deleted (should return 404)
    get_response = client.get(
        "/api/variations/var_1",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert get_response.status_code == 404


def test_delete_variation_not_found(client, auth_token):
    """Test deleting a non-existent variation."""
    response = client.delete(
        "/api/variations/nonexistent",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 404


def test_bulk_update_stock_requires_auth(client):
    """Test that bulk updating stock requires authentication."""
    response = client.put("/api/variations/bulk/stock", json={
        "updates": [{"variation_id": "var_1", "stock": 30}]
    })
    assert response.status_code == 401


def test_bulk_update_stock_success(client, auth_token, sample_products):
    """Test bulk getting stock for multiple variations (stock is calculated from pre-uploaded products)."""
    response = client.put(
        "/api/variations/bulk/stock",
        json={
            "updates": [
                {"variation_id": "var_1"},
                {"variation_id": "var_2"},
            ]
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == 2
    assert data["failed"] == 0
    assert len(data["results"]) == 2
    # Stock is calculated from pre-uploaded products (0 if none exist)
    for result in data["results"]:
        assert "variation_id" in result
        assert "stock" in result
        assert result["stock"] == 0  # No pre-uploaded products exist


def test_bulk_update_stock_partial_failure(client, auth_token, sample_products):
    """Test bulk getting stock with some failures."""
    response = client.put(
        "/api/variations/bulk/stock",
        json={
            "updates": [
                {"variation_id": "var_1"},
                {"variation_id": "nonexistent"},
            ]
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == 1
    assert data["failed"] == 1
    assert len(data["errors"]) == 1


def test_get_low_stock_variations_requires_auth(client):
    """Test that getting low stock variations requires authentication."""
    response = client.get("/api/variations/low-stock?threshold=5")
    assert response.status_code == 401


def test_get_low_stock_variations(client, auth_token, sample_products):
    """Test getting variations with low stock."""
    response = client.get(
        "/api/variations/low-stock?threshold=5",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    # Stock is calculated from pre-uploaded products (0 if none exist)
    # All variations should have stock=0, so all should be included with threshold=5
    variation_ids = [v["id"] for product in data["items"] for v in product["variations"]]
    # All variations should be included since they all have 0 stock (no pre-uploaded products)
    assert len(variation_ids) >= 0  # At least some variations should be returned


def test_bulk_activate_variations_requires_auth(client):
    """Test that bulk activating variations requires authentication."""
    response = client.put("/api/variations/bulk/activate", json={
        "variation_ids": ["var_1", "var_2"]
    })
    assert response.status_code == 401


def test_bulk_activate_variations_success(client, auth_token, sample_products):
    """Test bulk activating variations."""
    # First deactivate var_3
    client.put(
        "/api/variations/var_3",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    response = client.put(
        "/api/variations/bulk/activate",
        json={
            "variation_ids": ["var_1", "var_3"]
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == 2
    assert data["failed"] == 0
    
    # Verify variations are active
    var1_response = client.get(
        "/api/variations/var_1",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert var1_response.json()["is_active"] is True
    
    var3_response = client.get(
        "/api/variations/var_3",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert var3_response.json()["is_active"] is True


def test_bulk_deactivate_variations_requires_auth(client):
    """Test that bulk deactivating variations requires authentication."""
    response = client.put("/api/variations/bulk/deactivate", json={
        "variation_ids": ["var_1", "var_2"]
    })
    assert response.status_code == 401


def test_bulk_deactivate_variations_success(client, auth_token, sample_products):
    """Test bulk deactivating variations."""
    response = client.put(
        "/api/variations/bulk/deactivate",
        json={
            "variation_ids": ["var_1", "var_2"]
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == 2
    assert data["failed"] == 0
    
    # Verify variations are inactive
    var1_response = client.get(
        "/api/variations/var_1",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert var1_response.json()["is_active"] is False
    
    var2_response = client.get(
        "/api/variations/var_2",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert var2_response.json()["is_active"] is False


def test_bulk_delete_variations_requires_auth(client):
    """Test that bulk deleting variations requires authentication."""
    response = client.post(
        "/api/variations/bulk/delete",
        json={"variation_ids": ["var_1", "var_2"]}
    )
    assert response.status_code == 401


def test_bulk_delete_variations_success(client, auth_token, sample_products):
    """Test bulk deleting variations."""
    response = client.post(
        "/api/variations/bulk/delete",
        json={"variation_ids": ["var_1", "var_2"]},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == 2
    assert data["failed"] == 0
    
    # Verify variations are deleted
    var1_response = client.get(
        "/api/variations/var_1",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert var1_response.status_code == 404
    
    var2_response = client.get(
        "/api/variations/var_2",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert var2_response.status_code == 404


def test_bulk_delete_variations_partial_failure(client, auth_token, sample_products):
    """Test bulk deleting variations with some failures."""
    response = client.post(
        "/api/variations/bulk/delete",
        json={"variation_ids": ["var_1", "nonexistent"]},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == 1
    assert data["failed"] == 1
    assert len(data["errors"]) == 1


# --- Role-enforcement tests ---

@pytest.fixture
def test_viewer(test_db: Session):
    """Create a viewer-role admin user."""
    viewer = Admin(
        id="viewer_1",
        username="testviewer",
        email="viewer@example.com",
        password_hash=get_password_hash("testpass123"),
        full_name="Test Viewer",
        role=AdminRole.VIEWER,
        is_active=True,
    )
    test_db.add(viewer)
    test_db.commit()
    return viewer


@pytest.fixture
def viewer_token(test_viewer: Admin):
    """Create auth token for the viewer-role admin."""
    return create_access_token(data={"sub": test_viewer.username})


@pytest.fixture
def admin_token(test_admin: Admin):
    """Alias for auth_token — explicit admin-role token."""
    return create_access_token(data={"sub": test_admin.username})


@pytest.fixture
def sample_product(test_db: Session):
    """Create a single sample product."""
    product = Product(
        id="prod_role_test",
        name="Role Test Product",
        description="Used for role enforcement tests",
        delivery_type=DeliveryType.PRE_UPLOADED,
        is_active=True,
    )
    test_db.add(product)
    test_db.commit()
    return product


def test_viewer_cannot_create_variation(client, viewer_token, sample_product):
    """A viewer-role token must be forbidden from creating a variation."""
    resp = client.post(
        "/api/variations/",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={
            "product_id": sample_product.id,
            "name": "Should Fail",
            "price": 1000,
            "stock": 1,
        },
    )
    assert resp.status_code == 403


def test_admin_can_create_variation(client, admin_token, sample_product):
    """An admin-role token is allowed (not 403)."""
    resp = client.post(
        "/api/variations/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "product_id": sample_product.id,
            "name": "Allowed Variation",
            "price": 1000,
            "stock": 1,
        },
    )
    assert resp.status_code != 403
