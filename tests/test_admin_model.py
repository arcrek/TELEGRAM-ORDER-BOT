"""
Tests for Admin model.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models.admin import Admin, AdminRole
from src.database.models.base import Base


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestAdminModel:
    """Test Admin model."""

    def test_create_admin(self, db_session):
        """Test creating an admin."""
        admin = Admin(
            id="admin_123",
            username="testadmin",
            email="test@example.com",
            password_hash="hashed_password",
            full_name="Test Admin",
            role=AdminRole.ADMIN,
            is_active=True,
        )
        db_session.add(admin)
        db_session.commit()

        retrieved = db_session.query(Admin).filter_by(id="admin_123").first()
        assert retrieved is not None
        assert retrieved.username == "testadmin"
        assert retrieved.email == "test@example.com"
        assert retrieved.full_name == "Test Admin"
        assert retrieved.role == AdminRole.ADMIN
        assert retrieved.is_active is True

    def test_admin_role_enum(self, db_session):
        """Test admin role enum values."""
        admin1 = Admin(
            id="admin_1",
            username="admin1",
            password_hash="hash1",
            full_name="Admin 1",
            role=AdminRole.ADMIN,
        )
        admin2 = Admin(
            id="admin_2",
            username="admin2",
            password_hash="hash2",
            full_name="Admin 2",
            role=AdminRole.VIEWER,
        )
        db_session.add_all([admin1, admin2])
        db_session.commit()

        assert admin1.role == AdminRole.ADMIN
        assert admin2.role == AdminRole.VIEWER

    def test_admin_unique_username(self, db_session):
        """Test admin username uniqueness."""
        admin1 = Admin(
            id="admin_1",
            username="testuser",
            password_hash="hash1",
            full_name="User 1",
        )
        db_session.add(admin1)
        db_session.commit()

        # Try to create duplicate username
        admin2 = Admin(
            id="admin_2",
            username="testuser",
            password_hash="hash2",
            full_name="User 2",
        )
        db_session.add(admin2)
        
        with pytest.raises(Exception):  # Should raise IntegrityError
            db_session.commit()

