"""
Tests for supplier service.
"""
import pytest

from src.database.services.supplier_service import SupplierService


@pytest.fixture
def db_session():
    """Create a test database session."""
    # Use in-memory SQLite for isolation
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.database.models.base import Base
    
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def supplier_service(db_session):
    """Create a supplier service instance."""
    return SupplierService(db_session)


class TestSupplierService:
    """Test SupplierService."""

    def test_generate_supplier_id(self, supplier_service):
        """Test supplier ID generation."""
        supplier_id = supplier_service.generate_supplier_id()
        assert supplier_id.startswith("supp_")
        assert len(supplier_id) == 13  # "supp_" + 8 hex chars

    def test_create_supplier(self, supplier_service):
        """Test creating a supplier."""
        supplier = supplier_service.create_supplier(
            telegram_user_id=123456789,
            name="Test Supplier",
            is_active=True,
        )
        
        assert supplier is not None
        assert supplier.telegram_user_id == 123456789
        assert supplier.name == "Test Supplier"
        assert supplier.is_active is True
        assert supplier.id.startswith("supp_")

    def test_create_supplier_duplicate(self, supplier_service):
        """Test creating duplicate supplier fails."""
        supplier1 = supplier_service.create_supplier(
            telegram_user_id=123456789,
            name="Test Supplier 1",
        )
        assert supplier1 is not None
        
        # Try to create duplicate
        supplier2 = supplier_service.create_supplier(
            telegram_user_id=123456789,
            name="Test Supplier 2",
        )
        assert supplier2 is None

    def test_get_supplier_by_telegram_id(self, supplier_service):
        """Test getting supplier by Telegram ID."""
        created = supplier_service.create_supplier(
            telegram_user_id=123456789,
            name="Test Supplier",
        )
        
        retrieved = supplier_service.get_supplier_by_telegram_id(123456789)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.telegram_user_id == 123456789

    def test_get_supplier_by_telegram_id_not_found(self, supplier_service):
        """Test getting non-existent supplier."""
        retrieved = supplier_service.get_supplier_by_telegram_id(999999999)
        assert retrieved is None

    def test_get_supplier_by_id(self, supplier_service):
        """Test getting supplier by ID."""
        created = supplier_service.create_supplier(
            telegram_user_id=123456789,
            name="Test Supplier",
        )
        
        retrieved = supplier_service.get_supplier_by_id(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id

    def test_get_supplier_by_id_not_found(self, supplier_service):
        """Test getting non-existent supplier by ID."""
        retrieved = supplier_service.get_supplier_by_id("supp_nonexistent")
        assert retrieved is None

    def test_update_supplier_status(self, supplier_service):
        """Test updating supplier status."""
        supplier = supplier_service.create_supplier(
            telegram_user_id=123456789,
            name="Test Supplier",
            is_active=True,
        )
        
        updated = supplier_service.update_supplier_status(supplier.id, False)
        assert updated is not None
        assert updated.is_active is False
        
        # Verify in database
        retrieved = supplier_service.get_supplier_by_id(supplier.id)
        assert retrieved.is_active is False

    def test_update_supplier_status_not_found(self, supplier_service):
        """Test updating non-existent supplier."""
        updated = supplier_service.update_supplier_status("supp_nonexistent", False)
        assert updated is None

    def test_is_supplier_registered(self, supplier_service):
        """Test checking if supplier is registered."""
        # Not registered
        assert supplier_service.is_supplier_registered(123456789) is False
        
        # Register
        supplier = supplier_service.create_supplier(
            telegram_user_id=123456789,
            name="Test Supplier",
            is_active=True,
        )
        
        # Check registered
        assert supplier_service.is_supplier_registered(123456789) is True
        
        # Deactivate
        supplier_service.update_supplier_status(supplier.id, False)
        
        # Check not registered (inactive)
        assert supplier_service.is_supplier_registered(123456789) is False

