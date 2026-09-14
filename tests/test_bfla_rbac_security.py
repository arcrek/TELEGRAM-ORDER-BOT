"""
Regression tests for Broken Function Level Authorization (BFLA) hardening ([CRIT-02]).

Verifies that:
1. Authenticated users with role='viewer' receive HTTP 403 Forbidden on all mutating endpoints:
   - PUT /api/orders/{id}/status
   - POST /api/products
   - PUT /api/products/{id}
   - DELETE /api/products/{id}
   - POST /api/variations/{id}/bonus-tiers
   - PUT /api/bonus-tiers/{id}
   - DELETE /api/bonus-tiers/{id}
   - POST /api/variations/{id}/discount-tiers
   - PUT /api/discount-tiers/{id}
   - DELETE /api/discount-tiers/{id}
   - POST /api/products/upload
2. Authenticated users with role='admin' are authorized (status code is not 403).
"""

import atexit
import contextlib
import os
import tempfile
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.dashboard.auth import create_access_token, get_db
from src.dashboard.main import app
from src.database.models import Admin, AdminRole, Base

with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as test_db_file:
    test_db_path = test_db_file.name


def cleanup_test_db():
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
    Base.metadata.create_all(test_engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def setup_database():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def viewer_auth():
    session = TestSession()
    try:
        viewer = Admin(
            id="admin_viewer_01",
            username="viewer_user",
            password_hash="fake_hash",
            full_name="Viewer User",
            role=AdminRole.VIEWER,
            is_active=True,
        )
        session.add(viewer)
        session.commit()
        token = create_access_token(
            data={"sub": viewer.username, "role": viewer.role.value, "admin_id": viewer.id},
            expires_delta=timedelta(minutes=30),
        )
        return {"Authorization": f"Bearer {token}"}
    finally:
        session.close()


@pytest.fixture
def admin_auth():
    session = TestSession()
    try:
        admin = Admin(
            id="admin_full_01",
            username="admin_user",
            password_hash="fake_hash",
            full_name="Full Admin User",
            role=AdminRole.ADMIN,
            is_active=True,
        )
        session.add(admin)
        session.commit()
        token = create_access_token(
            data={"sub": admin.username, "role": admin.role.value, "admin_id": admin.id},
            expires_delta=timedelta(minutes=30),
        )
        return {"Authorization": f"Bearer {token}"}
    finally:
        session.close()


MUTATING_ROUTES = [
    ("PUT", "/api/orders/ORD-TEST/status", {"status": "DELIVERED"}),
    ("POST", "/api/products", {"name": "Test Prod", "delivery_type": "pre_uploaded"}),
    ("PUT", "/api/products/PROD-TEST", {"name": "Updated Prod"}),
    ("DELETE", "/api/products/PROD-TEST", None),
    ("POST", "/api/variations/VAR-TEST/bonus-tiers", {"min_quantity": 2, "bonus_quantity": 1}),
    ("PUT", "/api/bonus-tiers/TIER-TEST", {"bonus_quantity": 2}),
    ("DELETE", "/api/bonus-tiers/TIER-TEST", None),
    ("POST", "/api/variations/VAR-TEST/discount-tiers", {"min_quantity": 5, "discount_percentage": 10.0}),
    ("PUT", "/api/discount-tiers/TIER-TEST", {"discount_percentage": 15.0}),
    ("DELETE", "/api/discount-tiers/TIER-TEST", None),
    ("POST", "/api/products/upload", {"variation_id": "VAR-TEST", "product_data_list": ["item1"]}),
]


@pytest.mark.parametrize("method,path,body", MUTATING_ROUTES)
def test_viewer_role_is_forbidden_on_mutating_routes(client, viewer_auth, method, path, body):
    """Viewer must receive HTTP 403 Forbidden on all mutating endpoints."""
    if method == "PUT":
        response = client.put(path, json=body, headers=viewer_auth)
    elif method == "POST":
        response = client.post(path, json=body, headers=viewer_auth)
    elif method == "DELETE":
        response = client.delete(path, headers=viewer_auth)
    else:
        raise ValueError(f"Unsupported test method: {method}")

    assert response.status_code == 403, (
        f"Expected 403 for viewer on {method} {path}, got {response.status_code}: {response.text}"
    )


@pytest.mark.parametrize("method,path,body", MUTATING_ROUTES)
def test_admin_role_is_authorized_on_mutating_routes(client, admin_auth, method, path, body):
    """Admin must NOT receive HTTP 403 Forbidden on mutating endpoints."""
    if method == "PUT":
        response = client.put(path, json=body, headers=admin_auth)
    elif method == "POST":
        response = client.post(path, json=body, headers=admin_auth)
    elif method == "DELETE":
        response = client.delete(path, headers=admin_auth)
    else:
        raise ValueError(f"Unsupported test method: {method}")

    assert response.status_code != 403, (
        f"Admin was unexpectedly forbidden (403) on {method} {path}: {response.text}"
    )
