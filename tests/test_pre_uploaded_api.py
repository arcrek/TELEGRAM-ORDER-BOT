"""
Tests for the POST /pre-uploaded-products/export endpoint.
"""

import os
import atexit
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.dashboard.main import app
from src.dashboard.auth import get_db, get_password_hash, create_access_token
from src.database.models.base import Base
from src.database.models.admin import Admin, AdminRole
from src.database.models.product import Product
from src.database.models.product_variation import ProductVariation
from src.database.models.pre_uploaded_product import PreUploadedProduct
from src.database.models.enums import DeliveryType

# Import all models so they're registered with Base.metadata
from src.database.models import *  # noqa: F401, F403

# ── Test DB setup ─────────────────────────────────────────────────────────────

test_db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
test_db_path = test_db_file.name
test_db_file.close()


def _cleanup_test_db() -> None:
    try:
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)
    except Exception:
        pass


atexit.register(_cleanup_test_db)

test_engine = create_engine(
    f"sqlite:///{test_db_path}",
    echo=False,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)
Base.metadata.create_all(test_engine)
TestSession = sessionmaker(bind=test_engine)


def override_get_db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


# ── Pytest fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True, scope="function")
def reset_database():
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield
    with test_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.commit()


@pytest.fixture
def test_db():
    session = TestSession()
    yield session
    session.close()


@pytest.fixture
def admin_user(test_db: Session) -> Admin:
    admin = Admin(
        id="admin_export_1",
        username="exportadmin",
        email="exportadmin@test.com",
        password_hash=get_password_hash("adminpass"),
        full_name="Export Admin",
        role=AdminRole.ADMIN,
        is_active=True,
    )
    test_db.add(admin)
    test_db.commit()
    return admin


@pytest.fixture
def viewer_user(test_db: Session) -> Admin:
    viewer = Admin(
        id="viewer_export_1",
        username="exportviewer",
        email="exportviewer@test.com",
        password_hash=get_password_hash("viewerpass"),
        full_name="Export Viewer",
        role=AdminRole.VIEWER,
        is_active=True,
    )
    test_db.add(viewer)
    test_db.commit()
    return viewer


@pytest.fixture
def admin_token(admin_user: Admin) -> str:
    return create_access_token(data={"sub": admin_user.username})


@pytest.fixture
def viewer_token(viewer_user: Admin) -> str:
    return create_access_token(data={"sub": viewer_user.username})


@pytest.fixture
def product_and_variation(test_db: Session):
    """Create a PRE_UPLOADED product and one variation."""
    product = Product(
        id="prod_export",
        name="Export Product",
        description="Test",
        delivery_type=DeliveryType.PRE_UPLOADED,
        is_active=True,
    )
    test_db.add(product)

    variation = ProductVariation(
        id="var_export",
        product_id="prod_export",
        name="Export Variation",
        price=100000,
        stock=20,
        is_active=True,
    )
    test_db.add(variation)
    test_db.commit()
    return product, variation


@pytest.fixture
def stock_rows(test_db: Session, product_and_variation):
    """Add 5 available pre-uploaded rows."""
    product, variation = product_and_variation
    rows = []
    for i in range(5):
        row = PreUploadedProduct(
            id=f"stock_{i}",
            product_id=product.id,
            variation_id=variation.id,
            product_data=f"data_item_{i}",
            is_used=False,
        )
        test_db.add(row)
        rows.append(row)
    test_db.commit()
    return rows


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_export_requires_admin_role(client, viewer_token, product_and_variation):
    """Viewer role must receive 403 Forbidden."""
    product, variation = product_and_variation
    response = client.post(
        "/api/pre-uploaded-products/export",
        json={"product_id": product.id, "variation_id": variation.id, "amount": 1},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 403


def test_export_success(client, admin_token, product_and_variation, stock_rows):
    """Successful export of 2 items returns exported=2, short=False, 2 data entries."""
    product, variation = product_and_variation
    response = client.post(
        "/api/pre-uploaded-products/export",
        json={"product_id": product.id, "variation_id": variation.id, "amount": 2},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requested"] == 2
    assert body["exported"] == 2
    assert body["short"] is False
    assert len(body["data"]) == 2


def test_export_short_stock(client, admin_token, product_and_variation, test_db):
    """Request more than available → partial export with short=True."""
    product, variation = product_and_variation
    # Add exactly 3 rows
    for i in range(3):
        test_db.add(
            PreUploadedProduct(
                id=f"short_{i}",
                product_id=product.id,
                variation_id=variation.id,
                product_data=f"short_data_{i}",
                is_used=False,
            )
        )
    test_db.commit()

    response = client.post(
        "/api/pre-uploaded-products/export",
        json={"product_id": product.id, "variation_id": variation.id, "amount": 10},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["exported"] == 3
    assert body["short"] is True


def test_export_zero_available(client, admin_token, product_and_variation):
    """No available rows → exported=0, short=True, not an HTTP error."""
    product, variation = product_and_variation
    response = client.post(
        "/api/pre-uploaded-products/export",
        json={"product_id": product.id, "variation_id": variation.id, "amount": 5},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["exported"] == 0
    assert body["short"] is True
    assert body["data"] == []


def test_export_amount_zero_rejected(client, admin_token, product_and_variation):
    """amount=0 must be rejected with 422 Unprocessable Entity."""
    product, variation = product_and_variation
    response = client.post(
        "/api/pre-uploaded-products/export",
        json={"product_id": product.id, "variation_id": variation.id, "amount": 0},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 422


def test_export_amount_negative_rejected(client, admin_token, product_and_variation):
    """Negative amount must be rejected with 422."""
    product, variation = product_and_variation
    response = client.post(
        "/api/pre-uploaded-products/export",
        json={"product_id": product.id, "variation_id": variation.id, "amount": -5},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 422


def test_export_amount_exceeds_max_rejected(client, admin_token, product_and_variation):
    """amount > 1000 must be rejected with 422."""
    product, variation = product_and_variation
    response = client.post(
        "/api/pre-uploaded-products/export",
        json={"product_id": product.id, "variation_id": variation.id, "amount": 1001},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 422


def test_export_variation_mismatch(client, admin_token, product_and_variation, test_db):
    """Variation that belongs to a different product → 400 Bad Request."""
    product, variation = product_and_variation

    # Create a second product with its own variation
    other_product = Product(
        id="prod_other",
        name="Other Product",
        description="Other",
        delivery_type=DeliveryType.PRE_UPLOADED,
        is_active=True,
    )
    test_db.add(other_product)
    other_variation = ProductVariation(
        id="var_other",
        product_id="prod_other",
        name="Other Variation",
        price=50000,
        stock=5,
        is_active=True,
    )
    test_db.add(other_variation)
    test_db.commit()

    # Pass other_variation with original product → mismatch
    response = client.post(
        "/api/pre-uploaded-products/export",
        json={
            "product_id": product.id,
            "variation_id": other_variation.id,
            "amount": 1,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 400
