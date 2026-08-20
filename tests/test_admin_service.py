"""
Tests for admin service.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.admin import AdminRole
from src.database.models.base import Base
from src.database.services.admin_service import AdminService


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def admin_service(db_session):
    """Create an admin service instance."""
    return AdminService(db_session)


class TestAdminService:
    """Test AdminService."""

    def test_generate_admin_id(self, admin_service):
        """Test admin ID generation."""
        admin_id = admin_service.generate_admin_id()
        assert admin_id.startswith("admin_")
        assert len(admin_id) == 14  # "admin_" + 8 hex chars

    def test_create_admin(self, admin_service):
        """Test creating an admin."""
        admin = admin_service.create_admin(
            username="testadmin",
            password_hash="hashed_password",
            full_name="Test Admin",
            email="test@example.com",
            role=AdminRole.ADMIN,
        )
        
        assert admin is not None
        assert admin.username == "testadmin"
        assert admin.email == "test@example.com"
        assert admin.full_name == "Test Admin"
        assert admin.role == AdminRole.ADMIN
        assert admin.is_active is True
        assert admin.id.startswith("admin_")

    def test_get_admin_by_username(self, admin_service):
        """Test getting admin by username."""
        created = admin_service.create_admin(
            username="testadmin",
            password_hash="hash",
            full_name="Test Admin",
        )
        
        retrieved = admin_service.get_admin_by_username("testadmin")
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.username == "testadmin"

    def test_get_admin_by_username_not_found(self, admin_service):
        """Test getting non-existent admin."""
        retrieved = admin_service.get_admin_by_username("nonexistent")
        assert retrieved is None

    def test_get_admin_by_username_inactive(self, admin_service):
        """Test that inactive admins are not returned."""
        admin = admin_service.create_admin(
            username="inactive",
            password_hash="hash",
            full_name="Inactive Admin",
        )
        admin_service.update_admin_status(admin.id, False)
        
        retrieved = admin_service.get_admin_by_username("inactive")
        assert retrieved is None

    def test_get_admin_by_id(self, admin_service):
        """Test getting admin by ID."""
        created = admin_service.create_admin(
            username="testadmin",
            password_hash="hash",
            full_name="Test Admin",
        )
        
        retrieved = admin_service.get_admin_by_id(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id

    def test_get_admin_by_id_not_found(self, admin_service):
        """Test getting non-existent admin by ID."""
        retrieved = admin_service.get_admin_by_id("admin_nonexistent")
        assert retrieved is None

    def test_update_admin_status(self, admin_service):
        """Test updating admin status."""
        admin = admin_service.create_admin(
            username="testadmin",
            password_hash="hash",
            full_name="Test Admin",
        )
        
        updated = admin_service.update_admin_status(admin.id, False)
        assert updated is not None
        assert updated.is_active is False
        
        # Verify in database
        retrieved = admin_service.get_admin_by_id(admin.id)
        assert retrieved.is_active is False

    def test_update_admin_status_not_found(self, admin_service):
        """Test updating non-existent admin."""
        updated = admin_service.update_admin_status("admin_nonexistent", False)
        assert updated is None

    def test_list_admins(self, admin_service):
        """Test listing admins."""
        admin1 = admin_service.create_admin(
            username="admin1",
            password_hash="hash1",
            full_name="Admin 1",
        )
        admin2 = admin_service.create_admin(
            username="admin2",
            password_hash="hash2",
            full_name="Admin 2",
        )
        admin3 = admin_service.create_admin(
            username="admin3",
            password_hash="hash3",
            full_name="Admin 3",
        )
        admin_service.update_admin_status(admin3.id, False)
        
        # List active only
        active_admins = admin_service.list_admins(include_inactive=False)
        assert len(active_admins) == 2
        assert admin1.id in [a.id for a in active_admins]
        assert admin2.id in [a.id for a in active_admins]
        
        # List all
        all_admins = admin_service.list_admins(include_inactive=True)
        assert len(all_admins) == 3

