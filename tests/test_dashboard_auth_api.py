"""
Tests for dashboard authentication API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models.base import Base
from src.database.models.admin import Admin, AdminRole
from src.dashboard.auth import get_db
from src.dashboard.main import app

# Import all models to ensure they're registered with Base
from src.database.models import *  # noqa: F401, F403

# Create test database with thread safety for SQLite
# Use a file-based database for tests to ensure table persistence across connections
import tempfile
import os
import atexit

test_db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
test_db_path = test_db_file.name
test_db_file.close()

# Clean up test database file on exit
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
# Create all tables once
Base.metadata.create_all(test_engine)
TestSession = sessionmaker(bind=test_engine)


def override_get_db():
    """Override get_db dependency for testing."""
    # Ensure tables exist before creating session
    Base.metadata.create_all(test_engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True, scope="function")
def setup_database():
    """Set up test database before each test."""
    # Drop and recreate tables for each test to ensure clean state
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield
    # Clean up after test - clear data but keep tables
    with test_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.commit()


@pytest.fixture
def client():
    """Create test client."""
    # Ensure tables exist before creating client
    Base.metadata.create_all(test_engine)
    return TestClient(app)


@pytest.fixture
def test_admin():
    """Create a test admin."""
    # Use bcrypt directly to avoid passlib initialization issue
    import bcrypt
    password_hash = bcrypt.hashpw(b"testpassword", bcrypt.gensalt()).decode('utf-8')
    
    # Ensure table exists
    Base.metadata.create_all(test_engine)
    
    session = TestSession()
    try:
        admin = Admin(
            id="admin_test123",
            username="testadmin",
            email="test@example.com",
            password_hash=password_hash,
            full_name="Test Admin",
            role=AdminRole.ADMIN,
            is_active=True,
        )
        session.add(admin)
        session.commit()
        session.refresh(admin)
        yield admin
    finally:
        session.close()


class TestAuthEndpoints:
    """Test authentication endpoints."""

    def test_login_success(self, client, test_admin):
        """Test successful login."""
        response = client.post(
            "/api/auth/login",
            data={
                "username": "testadmin",
                "password": "testpassword",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0

    def test_login_wrong_password(self, client, test_admin):
        """Test login with wrong password."""
        response = client.post(
            "/api/auth/login",
            data={
                "username": "testadmin",
                "password": "wrongpassword",
            },
        )
        
        assert response.status_code == 401
        assert "detail" in response.json()

    def test_login_nonexistent_user(self, client):
        """Test login with non-existent user."""
        response = client.post(
            "/api/auth/login",
            data={
                "username": "nonexistent",
                "password": "password",
            },
        )
        
        assert response.status_code == 401

    def test_get_current_user_with_token(self, client, test_admin):
        """Test getting current user with valid token."""
        # Login first
        login_response = client.post(
            "/api/auth/login",
            data={
                "username": "testadmin",
                "password": "testpassword",
            },
        )
        token = login_response.json()["access_token"]
        
        # Get current user
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testadmin"
        assert data["email"] == "test@example.com"
        assert data["full_name"] == "Test Admin"
        assert data["role"] == AdminRole.ADMIN.value

    def test_get_current_user_without_token(self, client):
        """Test getting current user without token."""
        response = client.get("/api/auth/me")
        
        assert response.status_code == 401

    def test_get_current_user_invalid_token(self, client):
        """Test getting current user with invalid token."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token"},
        )
        
        assert response.status_code == 401

    def test_register_admin_success(self, client, test_admin):
        """Test registering a new admin (requires admin role)."""
        # Login as admin first
        login_response = client.post(
            "/api/auth/login",
            data={
                "username": "testadmin",
                "password": "testpassword",
            },
        )
        token = login_response.json()["access_token"]
        
        # Register new admin
        response = client.post(
            "/api/auth/register",
            json={
                "username": "newadmin",
                "email": "new@example.com",
                "password": "newpassword",
                "full_name": "New Admin",
                "role": AdminRole.VIEWER.value,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newadmin"
        assert data["email"] == "new@example.com"
        assert data["role"] == AdminRole.VIEWER.value

    def test_register_admin_duplicate_username(self, client, test_admin):
        """Test registering admin with duplicate username."""
        # Login as admin first
        login_response = client.post(
            "/api/auth/login",
            data={
                "username": "testadmin",
                "password": "testpassword",
            },
        )
        token = login_response.json()["access_token"]
        
        # Try to register with existing username
        response = client.post(
            "/api/auth/register",
            json={
                "username": "testadmin",  # Already exists
                "email": "duplicate@example.com",
                "password": "password",
                "full_name": "Duplicate Admin",
                "role": AdminRole.VIEWER.value,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    def test_register_admin_requires_admin_role(self, client, setup_database):
        """Test that registration requires admin role."""
        # Create a viewer user using bcrypt directly
        import bcrypt
        password_hash = bcrypt.hashpw(b"viewerpass", bcrypt.gensalt()).decode('utf-8')
        
        session = TestSession()
        try:
            viewer = Admin(
                id="admin_viewer",
                username="viewer",
                password_hash=password_hash,
                full_name="Viewer User",
                role=AdminRole.VIEWER,
                is_active=True,
            )
            session.add(viewer)
            session.commit()
        finally:
            session.close()
        
        # Login as viewer
        login_response = client.post(
            "/api/auth/login",
            data={
                "username": "viewer",
                "password": "viewerpass",
            },
        )
        token = login_response.json()["access_token"]
        
        # Try to register (should fail)
        response = client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "password": "password",
                "full_name": "New User",
                "role": AdminRole.VIEWER.value,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 403

